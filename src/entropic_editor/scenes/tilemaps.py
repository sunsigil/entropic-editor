import csv;
import cowtools;
import sprites;
import math;

def dense_to_sparse(src):
	dst = [];
	dx, dy = src["position"];
	for row in range(src["rows"]):
		for col in range(src["columns"]):
			idx = row * src["columns"] + col;
			frame_idx = src["frame_indices"][idx]-1;
			if frame_idx >= 0:
				dst.append({
					"position": [col * 16 + dx, row * 16 + dy],
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
	dst["rows"] = int(max_y - min_y + 16)//16;
	dst["columns"] = int(max_x - min_x + 16)//16;
	dst["frame_indices"] = [0 for i in range(dst["rows"]*dst["columns"])];

	dx, dy = dst["position"];
	for tile in src:
		x, y = tile["position"];
		x, y = (x-dx)//16, (y-dy)//16;
		idx = int(y) * dst["columns"] + int(x);
		if idx < len(dst["frame_indices"]):
			dst["frame_indices"][idx] = tile["frame_idx"]+1;

	return dst;

def import_tilemap(csv_path):
	with open(csv_path) as file:
		reader = csv.reader(file);
		asset_data = {
			"rows": 0,
			"columns": 0,
			"frame_indices": []
		};
		for row in reader:
			for col in row:
				["frame_indices"].append(int(col));
			asset_data["rows"] += 1;
			asset_data["columns"] = len(row);
		return asset_data;

def export_tilemap(tilemap, csv_path):
	with open(csv_path) as file:
		rows = [];
		match tilemap["type"]:
			case "dense":
				for row_idx in range(tilemap["dense"]["rows"]):
					row = [];
					for col_idx in range(tilemap["dense"]["cols"]):
						idx = row_idx * tilemap["dense"]["cols"] + col_idx;
						row.append(tilemap["dense"]["frame_indices"][idx]);
					rows.append(row);
		writer = csv.writer(file);
		writer.writerows(rows);

def spatial_search(tilemap, x, y):
	x = cowtools.align(x, 16);
	y = cowtools.align(y, 16);
	match tilemap["type"]:
		case "dense":
			idx = y * tilemap["dense"]["columns"] + x;
			if idx >= 0 and idx < len(tilemap["dense"]["frame_indices"]):
				return tilemap["dense"]["frame_indices"][idx];
			return None;
		case "sparse":
			return next((x for x in tilemap["sparse"] if x["position"][0] == x and x["position"][1] == y), None);

def place_tile(tilemap, frame_idx, x, y):
	x = cowtools.align(x, 16, mapping=math.floor);
	y = cowtools.align(y, 16, mapping=math.floor);
	match tilemap["type"]:
		case "dense":
			idx = y * tilemap["dense"]["columns"] + x;
			if idx >= 0 and idx < len(tilemap["dense"]["frame_indices"]):
				tilemap["dense"]["frame_indices"][idx] = frame_idx;
		case "sparse":
			existing = spatial_search(tilemap, x, y);
			if existing == None:
				tilemap["sparse"].append({
					"position": [x, y],
					"frame_idx": frame_idx
				});
			else:
				existing["frame_idx"] = frame_idx;

def clear_tile(tilemap, x, y):
	x = cowtools.align(x, 16, mapping=math.floor);
	y = cowtools.align(y, 16, mapping=math.floor);
	match tilemap["type"]:
		case "dense":
			data = tilemap["dense"];
			idx = y * data["columns"] + x;
			if idx >= 0 and idx < len(data["frame_indices"]):
				data["frame_indices"][idx] = 0;
		case "sparse":
			existing = spatial_search(tilemap, x, y);
			if existing != None:
				tilemap["sparse"].remove(existing);

def canvas_draw(canvas, tilemap, cursor=None):
	palette = sprites.SpriteBank.search(tilemap["palette"]);

	match tilemap["type"]:
		case "sparse":
			for tile in tilemap["sparse"]:
				frame_idx = cowtools.clamp(tile["frame_idx"], 0, palette.frame_count-1);
				canvas.draw_image(
					tile["position"][0], tile["position"][1],
					palette.frame_images[frame_idx]
				);

			if cursor != None:
				x, y = cursor;
				x0 = cowtools.align(x, 16, mapping=math.floor);
				y0 = cowtools.align(y, 16, mapping=math.floor);
				x1, y1 = x0+16, y0+16;
				canvas.draw_aabb(
					(x0, y0, x1, y1),
					(255, 255, 255),
				);
		
		case "dense":
			x0, y0 = tilemap["dense"]["position"];
			w = tilemap["dense"]["columns"];
			h = tilemap["dense"]["rows"];

			for row in range(h):
				y = y0 + row * 16;
				for col in range(w):
					x = x0 + col * 16;
					frame_idx = tilemap["dense"]["frame_indices"][row * w + col]-1;
					if frame_idx >= 0:
						frame_idx = cowtools.clamp(frame_idx, 0, palette.frame_count-1);
						canvas.draw_image(
							x, y,
							palette.frame_images[frame_idx]
						);