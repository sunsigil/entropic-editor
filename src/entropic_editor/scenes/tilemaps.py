import csv;
import cowtools;
import sprites;
import math;
import os;

TILE = 16;
# frame indices are stored 1-based in a uint8_t array on the runtime side
MAX_FRAME = 254;

def get_origin(tilemap):
	if tilemap["type"] == "dense":
		return tilemap["dense"]["position"];
	return [0, 0];

def world_to_cell(tilemap, x, y):
	ox, oy = get_origin(tilemap);
	return int(math.floor((x-ox)/TILE)), int(math.floor((y-oy)/TILE));

def cell_to_world(tilemap, col, row):
	ox, oy = get_origin(tilemap);
	return ox + col*TILE, oy + row*TILE;

def get_cell_aabb(tilemap, col0, row0, col1=None, row1=None):
	col1 = col0 if col1 == None else col1;
	row1 = row0 if row1 == None else row1;
	x0, y0 = cell_to_world(tilemap, min(col0, col1), min(row0, row1));
	x1, y1 = cell_to_world(tilemap, max(col0, col1)+1, max(row0, row1)+1);
	return (x0, y0, x1, y1);

class CellView:
	"""Cell-space accessor for either representation. Sparse tilemaps get a
	(col, row) index so a batch edit doesn't rescan the list for every cell."""
	def __init__(self, tilemap):
		self.tilemap = tilemap;
		self.dense = tilemap["dense"] if tilemap["type"] == "dense" else None;
		self.index = None;

		if self.dense == None:
			self.index = {};
			for tile in tilemap["sparse"]:
				self.index[world_to_cell(tilemap, *tile["position"])] = tile;

	def bounds(self):
		"""Inclusive (col0, row0, col1, row1), or None when there is nothing to bound."""
		if self.dense != None:
			if self.dense["rows"] <= 0 or self.dense["columns"] <= 0:
				return None;
			return (0, 0, self.dense["columns"]-1, self.dense["rows"]-1);

		if len(self.index) == 0:
			return None;
		cols = [key[0] for key in self.index];
		rows = [key[1] for key in self.index];
		return (min(cols), min(rows), max(cols), max(rows));

	def _dense_index(self, col, row):
		w, h = self.dense["columns"], self.dense["rows"];
		if col < 0 or col >= w or row < 0 or row >= h:
			return None;
		idx = row * w + col;
		if idx >= len(self.dense["frame_indices"]):
			return None;
		return idx;

	def get(self, col, row):
		"""Frame index of a cell, or None when empty or out of bounds."""
		if self.dense != None:
			idx = self._dense_index(col, row);
			if idx == None:
				return None;
			frame_idx = self.dense["frame_indices"][idx]-1;
			return frame_idx if frame_idx >= 0 else None;

		tile = self.index.get((col, row));
		return tile["frame_idx"] if tile != None else None;

	def set(self, col, row, frame_idx):
		"""frame_idx of None clears the cell."""
		if frame_idx != None:
			frame_idx = cowtools.clamp(int(frame_idx), 0, MAX_FRAME);

		if self.dense != None:
			idx = self._dense_index(col, row);
			if idx != None:
				self.dense["frame_indices"][idx] = 0 if frame_idx == None else frame_idx+1;
			return;

		existing = self.index.get((col, row));

		if frame_idx == None:
			if existing != None:
				sparse = self.tilemap["sparse"];
				for i, tile in enumerate(sparse):
					if tile is existing:
						del sparse[i];
						break;
				del self.index[(col, row)];
			return;

		if existing != None:
			existing["frame_idx"] = frame_idx;
		else:
			x, y = cell_to_world(self.tilemap, col, row);
			tile = {
				"position": [x, y],
				"frame_idx": frame_idx
			};
			self.tilemap["sparse"].append(tile);
			self.index[(col, row)] = tile;

def get_tile(tilemap, col, row):
	return CellView(tilemap).get(col, row);

def set_tile(tilemap, col, row, frame_idx):
	CellView(tilemap).set(col, row, frame_idx);

def cell_line(col0, row0, col1, row1):
	"""Bresenham, inclusive of both ends."""
	dc = abs(col1-col0);
	dr = -abs(row1-row0);
	sc = 1 if col0 < col1 else -1;
	sr = 1 if row0 < row1 else -1;
	err = dc + dr;

	col, row = col0, row0;
	while True:
		yield col, row;
		if col == col1 and row == row1:
			return;
		e2 = 2*err;
		if e2 >= dr:
			err += dr;
			col += sc;
		if e2 <= dc:
			err += dc;
			row += sr;

def stroke(tilemap, col0, row0, col1, row1, frame_idx):
	"""A frame only samples the cursor once, so a fast drag has to be joined up."""
	view = CellView(tilemap);
	for col, row in cell_line(col0, row0, col1, row1):
		view.set(col, row, frame_idx);

def fill_rect(tilemap, col0, row0, col1, row1, frame_idx):
	view = CellView(tilemap);
	for row in range(min(row0, row1), max(row0, row1)+1):
		for col in range(min(col0, col1), max(col0, col1)+1):
			view.set(col, row, frame_idx);

def flood_fill(tilemap, col, row, frame_idx, limit=1<<16):
	"""4-connected fill. A sparse tilemap has no extent of its own, so the fill is
	bounded by the tiles it already has."""
	view = CellView(tilemap);
	bounds = view.bounds();
	if bounds == None:
		return;

	col0, row0, col1, row1 = bounds;
	if col < col0 or col > col1 or row < row0 or row > row1:
		return;

	target = view.get(col, row);
	if target == frame_idx:
		return;

	queue = [(col, row)];
	seen = {(col, row)};
	while len(queue) > 0 and len(seen) <= limit:
		c, r = queue.pop();
		if view.get(c, r) != target:
			continue;
		view.set(c, r, frame_idx);

		for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
			neighbour = (c+dc, r+dr);
			if neighbour in seen:
				continue;
			if neighbour[0] < col0 or neighbour[0] > col1:
				continue;
			if neighbour[1] < row0 or neighbour[1] > row1:
				continue;
			seen.add(neighbour);
			queue.append(neighbour);

def resize_dense(dense, rows, columns):
	"""frame_indices is a flat row-major buffer, so a resize has to reflow it or
	every row after the first shifts."""
	rows = max(int(rows), 0);
	columns = max(int(columns), 0);

	src = dense["frame_indices"];
	src_w, src_h = dense["columns"], dense["rows"];
	dst = [0 for i in range(rows*columns)];

	for row in range(min(rows, src_h)):
		for col in range(min(columns, src_w)):
			idx = row * src_w + col;
			if idx < len(src):
				dst[row * columns + col] = src[idx];

	dense["rows"] = rows;
	dense["columns"] = columns;
	dense["frame_indices"] = dst;

def dense_to_sparse(src):
	dst = [];
	dx, dy = src["position"];
	for row in range(src["rows"]):
		for col in range(src["columns"]):
			idx = row * src["columns"] + col;
			frame_idx = src["frame_indices"][idx]-1;
			if frame_idx >= 0:
				dst.append({
					"position": [col * TILE + dx, row * TILE + dy],
					"frame_idx": frame_idx
				});
	return dst;

def sparse_to_dense(src):
	dst = {
		"position": [0, 0],
		"rows": 0,
		"columns": 0,
		"frame_indices": []
	};

	if len(src) == 0:
		return dst;

	min_x = math.inf;
	min_y = math.inf;
	max_x = -math.inf;
	max_y = -math.inf;
	for tile in src:
		x, y = tile["position"];
		min_x = min(min_x, x);
		min_y = min(min_y, y);
		max_x = max(max_x, x);
		max_y = max(max_y, y);

	dst["position"] = [int(min_x), int(min_y)];
	dst["rows"] = int(max_y - min_y + TILE)//TILE;
	dst["columns"] = int(max_x - min_x + TILE)//TILE;
	dst["frame_indices"] = [0 for i in range(dst["rows"]*dst["columns"])];

	dx, dy = dst["position"];
	for tile in src:
		x, y = tile["position"];
		x, y = (x-dx)//TILE, (y-dy)//TILE;
		idx = int(y) * dst["columns"] + int(x);
		if idx < len(dst["frame_indices"]):
			dst["frame_indices"][idx] = cowtools.clamp(tile["frame_idx"], 0, MAX_FRAME)+1;

	return dst;

def _import_dense(csv_path):
	rows = [];
	with open(csv_path, "r", newline="") as file:
		for row in csv.reader(file):
			row = [cell for cell in row if cell.strip() != ""];
			if len(row) == 0:
				continue;
			rows.append([int(cell) for cell in row]);

	columns = max([len(row) for row in rows], default=0);
	if any(len(row) != columns for row in rows):
		print(f"{csv_path}: ragged rows, padding to {columns} columns");

	frame_indices = [];
	for row in rows:
		frame_indices.extend(row);
		frame_indices.extend([0 for i in range(columns-len(row))]);

	return {
		"rows": len(rows),
		"columns": columns,
		"frame_indices": frame_indices
	};

def import_tilemap(tilemap, csv_path):
	if len(csv_path) == 0:
		return;

	match tilemap["type"]:
		case "dense":
			tilemap["dense"].update(_import_dense(csv_path));
		case "sparse":
			dense = _import_dense(csv_path);
			dense["position"] = [0, 0];
			tilemap["sparse"] = dense_to_sparse(dense);

def _export_dense(dense, csv_path):
	directory = os.path.dirname(csv_path);
	if len(directory) > 0:
		os.makedirs(directory, exist_ok=True);

	with open(csv_path, "w", newline="") as file:
		rows = [];
		for row_idx in range(dense["rows"]):
			row = [];
			for col_idx in range(dense["columns"]):
				idx = row_idx * dense["columns"] + col_idx;
				row.append(dense["frame_indices"][idx]);
			rows.append(row);
		writer = csv.writer(file);
		writer.writerows(rows);

def export_tilemap(tilemap, csv_path):
	if len(csv_path) == 0:
		return;

	match tilemap["type"]:
		case "dense":
			_export_dense(tilemap["dense"], csv_path);
		case "sparse":
			_export_dense(sparse_to_dense(tilemap["sparse"]), csv_path);

def canvas_draw(canvas, tilemap):
	palette = sprites.SpriteBank.search(tilemap["palette"]);

	match tilemap["type"]:
		case "sparse":
			for tile in tilemap["sparse"]:
				frame_idx = cowtools.clamp(tile["frame_idx"], 0, palette.frame_count-1);
				canvas.draw_image(
					tile["position"][0], tile["position"][1],
					palette.frame_images[frame_idx]
				);
		
		case "dense":
			x0, y0 = tilemap["dense"]["position"];
			w = tilemap["dense"]["columns"];
			h = tilemap["dense"]["rows"];

			canvas.draw_circle(x0, y0, 4, (255, 255, 255));
			for row in range(h):
				y = y0 + row * TILE;
				for col in range(w):
					x = x0 + col * TILE;
					idx = row * w + col;
					frame_idx = tilemap["dense"]["frame_indices"][idx]-1;
					if frame_idx >= 0:
						frame_idx = cowtools.clamp(frame_idx, 0, palette.frame_count-1);
						canvas.draw_image(
							x, y,
							palette.frame_images[frame_idx]
						);
			canvas.draw_aabb((x0, y0, x0+w*TILE, y0+h*TILE), (255, 255, 255));
