from imgui_bundle import imgui;
import glfw;
import csv;
import copy;

from ee_cowtools import *;
from ee_canvas import *;
from ee_assets import *;
from ee_sprites import SpriteBank, EditorSprite, SpritePreview;
from ee_input import InputManager;
from ee_imgui import *;
from ee_geometry import *;

#########################################################
## HELPERS

def get_entity_sprite(entity):
	prototype = AssetManager.search("prototype", entity["prototype"]);
	if prototype == None:
		return None;
	return SpriteBank.search(prototype["sprite"], safe=False);

def get_entity_aabb(entity):
	x, y = entity["position"];

	prototype = AssetManager.search("prototype", entity["prototype"]);
	if prototype != None:
		sprite = SpriteBank.search(prototype["sprite"], safe=False);
		if sprite != None:
			return [x, y, x+sprite.frame_width, y+sprite.frame_height];
	
		if len(prototype["boxes"]) > 0:
			x0, y0, x1, y1 = math.inf, math.inf, -math.inf, -math.inf;
			for box in prototype["boxes"]:
				x0 = min(x0, box["aabb"][0]);
				y0 = min(y0, box["aabb"][1]);
				x1 = max(x1, box["aabb"][2]);
				y1 = max(y1, box["aabb"][3]);
			return [x0+x, y0+y, x1+x, y1+y];

	return [x, y, x+16, y+16];

def get_text_aabb(text):
	x0, y0 = text["position"];
	width = len(text["text"]) * 8 * text["scale"];
	x1, y1 = x0 + width, y0 + 8 * text["scale"];
	return [x0, y0, x1, y1];

def get_script_data(entity, key):
	return next((x for x in entity["script_data"] if x["key"] == key), None);
	
#########################################################
## SCENE EDITOR

class EditMode(Enum):
	ENTITIES = 0,
	TILEMAP = 1,
	WALLS = 2,
	DOORS = 3,
	TEXTS = 4,
	PROPERTIES = 4

class TilemapEditor:
	def __init__(self, parent):
		self.parent = parent;
		self.tilemap = None;
		self.selected_frame = 0;
	
	def _type(self):
		return self.tilemap["type"];
	def _data(self):
		match self._type():
			case "sparse":
				return self.tilemap["sparse"];
			case "dense":
				return self.tilemap["dense"];
	
	def _spatial_search(self, position):
		match self._type():
			case "sparse":
				x, y = self.parent.canvas_grid.snap_point(position);
				tile = next((t for t in self._data() if t["position"][0] == x and t["position"][1] == y), None);
				return tile;
			case "dense":
				x, y = self.parent.canvas_grid.snap_point(position);
				idx = y * self._data()["columns"] + x;
				return self._data()["frame_indices"][idx] != 0;
	def _is_occupied(self, position):
		return self._spatial_search(position) != None;

	def on_load_scene(self):
		self.tilemap = self.parent.scene["tilemap"];
	
	def _gui_draw_palette(self):
		sprite = SpriteBank.search(self.tilemap["palette"]);
		wdw_w = imgui.get_content_region_avail().x;
		cols = int(wdw_w // 72);
		rows = int(math.ceil(sprite.frame_count / cols)) if cols > 0 else 0;

		i = 0;
		for r in range(rows):
			for c in range(cols):
				if i < sprite.frame_count:
					tint = (0.5, 0.5, 0.5, 1) if i == self.selected_frame else (1, 1, 1, 1);
					if imgui.image_button(f"##{i}", imgui.ImTextureRef(sprite.frame_textures[i]), (64, 64), tint_col=tint):
						self.selected_frame = i;
					imgui.same_line();
				i += 1;
			imgui.new_line();
	
	def _load_csv(self):
		with open(self._data()["csv"]) as file:
			reader = csv.reader(file);
			self._data()["frame_indices"] = [];
			rows = 0;
			for row in reader:
				for col in row:
					self._data()["frame_indices"].append(int(col));
				rows += 1;
			self._data()["rows"] = rows;
			self._data()["columns"] = len(self._data()["frame_indices"])//rows;
	
	def _gui_draw_csv(self):
		_, self._data()["position"] = imgui.input_int2("Position", self._data()["position"]);
		
		last_csv = self._data()["csv"];
		self._data()["csv"] = eegui_input_file("CSV", self._data()["csv"], "*.csv");
		if self._data()["csv"] != last_csv:
			self._load_csv();
	
	def draw_gui(self):
		if self.tilemap == None:
			return;
	
		self.tilemap["palette"] = eegui_input_asset("##palette", self.tilemap["palette"], "sprite");
		if self.tilemap["palette"] == "":
			return;

		match self._type():
			case "sparse":
				self._gui_draw_palette();
			case "dense":
				self._gui_draw_csv();
	
	def _paint_tick(self):
		palette = SpriteBank.search(self.tilemap["palette"]);
		self.selected_frame = clamp(self.selected_frame, 0, palette.frame_count-1);

		if self.parent.canvas_io.is_cursor_in_bounds():
			if InputManager.is_held(glfw.MOUSE_BUTTON_LEFT):
				cursor = self.parent.canvas_io.get_cursor();
				tile_cursor = self.parent.canvas_grid.snap_point(cursor);

				if InputManager.is_held(glfw.KEY_LEFT_SHIFT):
					trash = [];
					for idx, tile in enumerate(self.tilemap["sparse"]):
						tx, ty = self.parent.canvas_grid.snap_point(tile["position"]);
						cx, cy = tile_cursor;
						if int(tx) == int(cx) and int(ty) == int(cy):
							trash.append(idx);
					process_trash(self.tilemap["sparse"], trash, indices=True);
	
				elif self.selected_frame != None:
					existing = self._spatial_search(tile_cursor);
					if existing == None:
						self.tilemap["sparse"].append({
							"position": list(tile_cursor),
							"frame_idx": self.selected_frame
						});
					else:
						existing["frame_idx"] = self.selected_frame;

	def tick(self):
		if self.tilemap == None:
			return;
		if self.tilemap["palette"] == "":
			return;
		match self._type():
			case "sparse":
				self._paint_tick();

class WallEditor:
	class PlaceModes(Enum):
		NONE = 0,
		AABB = 1,
		SEGMENT = 2

	def __init__(self, parent):
		self.parent = parent;
		self.walls = None;

		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(self.parent.canvas_io, self.event_queue);
		self.manip_registry = CanvasManipRegistry();

		self.context = {};
		self.place_mode = WallEditor.PlaceModes.NONE;
		self.selected = None;

	def on_load_scene(self):
		self.walls = self.parent.scene["walls"];
		self.canvas_manip.clear();
		self.manip_registry.clear();
		self.context.clear();
	
	def draw_gui(self):
		if self.walls == None:
			return;

		self.place_mode = eegui_input_enum("Place mode", self.place_mode, self.PlaceModes);

		for idx, wall in enumerate(self.walls):
			imgui.set_next_item_open(wall == self.selected);
			node_open = imgui.tree_node(f"Wall {idx}##{id(self.walls)}{idx}");

			trash = [];
			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("Delete"):
					trash.append(idx);
					imgui.close_current_popup();
				imgui.end_popup();
			process_trash(self.walls, trash, indices=True);

			if node_open:
				match wall["type"]:
					case "aabb":
						wall["aabb"] = eegui_input_aabb("AABB", wall["aabb"]);
					case "segment":
						wall["segment"][0] = eegui_input_vec2("A", wall["segment"][0]);
						wall["segment"][1] = eegui_input_vec2("B", wall["segment"][1]);
				imgui.tree_pop();

	def _is_selected(self, wall):
		return self.selected == wall;	

	def _synchronize_manip(self):
		def make_shape(wall):
			match wall["type"]:
				case "aabb":
					return CanvasManipRect(wall["aabb"]);
				case "segment":
					return CanvasManipSegment(wall["segment"]);
		shapes = [make_shape(x) for x in self.walls];
		
		self.manip_registry.update(self.walls, shapes);
		self.canvas_manip.synchronize(self.manip_registry);
	
	def _handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CanvasManipClick):
				hit = event.eeid != None;
				self.selected = self.manip_registry.search(event.eeid) if hit else None;

				if hit or InputManager.is_held(glfw.KEY_LEFT_SHIFT):
					continue;
				
				x, y = event.point;
				x0, y0 = self.parent.canvas_grid.snap_point(event.point);
				x1, y1 = x0+16, y0+16;
				new_wall = None;
				
				match self.place_mode:
					case WallEditor.PlaceModes.AABB:
						new_wall = {
							"type": "aabb",
							"aabb": [x0, y0, x1, y1]
						};

					case WallEditor.PlaceModes.SEGMENT:
						deltas = [abs(x-x0), abs(y-y0), abs(x-x1), abs(y-y1)];
						min_idx = min(range(len(deltas)), key=deltas.__getitem__);
						segment = None;
						if min_idx == 0:				
							segment = [[x0, y0], [x0, y1]];
						elif min_idx == 1:			
							segment = [[x0, y0], [x1, y0]];
						elif min_idx == 2:			
							segment = [[x1, y0], [x1, y1]];
						elif min_idx == 3:	
							segment = [[x0, y1], [x1, y1]];
						new_wall = {
							"type": "segment",
							"segment": segment
						};
				
				if new_wall != None:
					self.walls.append(new_wall);
					self.selected = new_wall;	

			if isinstance(event, CanvasManipDrag):
				if event.eeid == None:
					self.parent.view_drag_handler(event);
					continue;
				
				match event.signal:
					case CanvasManipDrag.Signal.START:
						wall = self.manip_registry.search(event.eeid);
						type = wall["type"];
						x, y = event.point;

						match type:
							case "aabb":
								x0, y0 = wall["aabb"][:2];
								self.context["delta"] = (x0 - x, y0 - y);
								self.context["inside"] = event.distance <= -1;
								self.context["edge"] = aabb_closest_edge(wall["aabb"], event.point);
							case "segment":
								x0, y0 = wall["segment"][0];
								self.context["delta"] = (x0 - x, y0 - y);
								a_dist = point_point_dist(wall["segment"][0], event.point);
								b_dist = point_point_dist(wall["segment"][1], event.point);
								self.context["inside"] = a_dist >= 4 and b_dist >= 4;
								self.context["end"] = segment_closest_end(wall["segment"], event.point);

					case CanvasManipDrag.Signal.TICK:
						wall = self.manip_registry.search(event.eeid);
						type = wall["type"];

						match type:
							case "aabb":
								if self.context["inside"]:
									point = event.point[0] + self.context["delta"][0], event.point[1] + self.context["delta"][1];
									point = self.parent.canvas_grid.snap_point(point);
									wall["aabb"] = relocate_aabb(wall["aabb"], point);
								else:
									point = self.parent.canvas_grid.snap_point(event.point);
									wall["aabb"] = shape_aabb(wall["aabb"], self.context["edge"], point);
							case "segment":
								if self.context["inside"]:
									point = event.point[0] + self.context["delta"][0], event.point[1] + self.context["delta"][1];
									point = self.parent.canvas_grid.snap_point(point);
									wall["segment"] = relocate_segment(wall["segment"], point);
								else:
									point = self.parent.canvas_grid.snap_point(event.point);
									wall["segment"] = shape_segment(wall["segment"], self.context["end"], point);
	
	def tick(self):
		if self.walls == None:
			return;
	
		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_D):
			if self.selected != None:
				self.walls.remove(self.selected);
				self.selected = None;
		
		self._synchronize_manip();
		self.canvas_manip.tick();
		self._handle_events();

class TextEditor:
	def __init__(self, parent):
		self.parent = parent;
		self.texts = None;

		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(self.parent.canvas_io, self.event_queue);
		self.manip_registry = CanvasManipRegistry();
		self.context = {};

	def on_load_scene(self):
		self.texts = self.parent.scene["texts"];
		self.canvas_manip.clear();
		self.manip_registry.clear();
		self.event_queue.clear();
		self.context.clear();
	
	def draw_gui(self):
		if self.texts == None:
			return;
	
		node_open = imgui.tree_node(f"Texts##{id(self.texts)}");

		if imgui.begin_popup_context_item():
			if imgui.menu_item_simple("New text"):
				self.texts.append({
					"text": "Hello, world!",
					"colour": [255, 255, 255],
					"scale": 1,
					"position": [0, 0]
				});
				imgui.close_current_popup();
			imgui.end_popup();

		if node_open:
			trash = [];

			for idx, text in enumerate(self.texts):
				node_open = imgui.tree_node(f"{idx}##{id(self.texts)}{idx}");

				if imgui.begin_popup_context_item():
					trash = [];
					if imgui.menu_item_simple("Delete"):
						trash.append(idx);
						imgui.close_current_popup();
					imgui.end_popup();

				if node_open:
					text["text"] = eegui_input_string("Text", text["text"]);
					text["colour"] = eegui_input_colour("Colour", text["colour"]);
					text["scale"] = eegui_input_int("Scale", text["scale"]);
					text["position"] = eegui_input_vec2("Position", text["position"]);
					imgui.tree_pop();
			
			process_trash(self.texts, trash, indices=True);
			imgui.tree_pop();
	
	def _synchronize_manip(self):
		indices = [i for i in range(len(self.texts))];

		def make_shape(idx):
			text = self.texts[idx];
			aabb = get_text_aabb(text);
			return CanvasManipRect(aabb);
		shapes = [make_shape(x) for x in indices];
		
		self.manip_registry.update(indices, shapes);
		self.canvas_manip.synchronize(self.manip_registry);
	
	def _move_text(self, text, point):
		x, y = point;
		text["position"][0] = int(x);
		text["position"][1] = int(y);
	
	def _handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CanvasManipDrag):
				if event.eeid != None:
					match event.signal:
						case CanvasManipDrag.Signal.START:
							text = self.texts[self.manip_registry.search(event.eeid)];
							self.context = {
								"delta": (text["position"][0] - event.point[0], text["position"][1] - event.point[1]),
							}
						case CanvasManipDrag.Signal.TICK:
							text = self.texts[self.manip_registry.search(event.eeid)];
							point = event.point[0] + self.context["delta"][0], event.point[1] + self.context["delta"][1];
							point = self.parent.canvas_grid.snap_point(point);
							self._move_text(text, point);
	
	def tick(self):
		if self.texts == None:
			return;
		
		self._synchronize_manip();
		self.canvas_manip.tick();
		self._handle_events();

class DoorEditor:
	class Door:
		def __init__(self, scene, entity):
			self.scene = scene;
			self.entity = entity;
			self.pointers = [];
		
		def update(self, doors):
			for door in doors:
				if door is self:
					continue;
				to_scene = get_script_data(door.entity, "to_scene");
				if to_scene == None or to_scene["value"] != self.scene["name"]:
					continue;
				to_entity = get_script_data(door.entity, "to_entity");
				if to_entity == None or to_entity["value"] != self.entity["name"]:
					continue;
				self.pointers.append(door);
	
		def points_to(self):
			to_scene = get_script_data(self.entity, "to_scene");
			to_entity = get_script_data(self.entity, "to_entity");
			return to_scene["value"] != "" and to_entity["value"] != "";

		def is_pointed_to(self):
			return len(self.pointers) > 0;

	class Selector:
		def __init__(self, parent, door):
			self.parent = parent;
			self.door = door;
			self.open = True;

		def draw(self):
			_, self.open = imgui.begin("Select door", self.open);
			for scene in self.parent.door_hierarchy:
				if imgui.collapsing_header(scene):
					imgui.push_id(scene);
					for door in self.parent.door_hierarchy[scene]:
						if door == self.door:
							continue;
						to_scene = get_script_data(self.door.entity, "to_scene");
						to_entity = get_script_data(self.door.entity, "to_entity");
						was_selected = door.entity["name"] == to_entity["value"];
						clicked, value = imgui.menu_item(door.entity["name"], "", was_selected);
						if clicked:
							if was_selected:
								to_scene["value"] = "";
								to_entity["value"] = "";
							else:
								to_scene["value"] = door.scene["name"];
								to_entity["value"] = door.entity["name"];
					imgui.pop_id();
			imgui.end();
	
	def __init__(self, parent):
		self.parent = parent;
		self.door_pool = [];
		self.door_hierarchy = {};

		self.selector = None;
	
	def poll_all_doors(self):
		self.door_pool = [];
		self.door_hierarchy = {};
		for scene in AssetManager.get_all("scene"):
			self.door_hierarchy[scene["name"]] = [];
			for entity in scene["entities"]:
				prototype = AssetManager.search("prototype", entity["prototype"]);
				if prototype == None:
					continue;
				if "door" in prototype["scripts"]:
					door = DoorEditor.Door(scene, entity);
					self.door_pool.append(door);
					self.door_hierarchy[scene["name"]].append(door);
	
	def logic(self):
		self.poll_all_doors();
		for door in self.door_pool:
			door.update(self.door_pool);
	
	def draw_gui(self):
		for scene in self.door_hierarchy:
			if scene == self.parent.scene["name"]:
				for door in self.door_hierarchy[scene]:
					if imgui.tree_node(door.entity["name"]):
						to_scene = get_script_data(door.entity, "to_scene");
						to_entity = get_script_data(door.entity, "to_entity");
						if AssetManager.search("scene", to_scene["value"]) == None:
							to_scene["value"] = "";
						elif next((x for x in AssetManager.search("scene", to_scene["value"])["entities"] if x["name"] == to_entity["value"]), None) == None:
							to_entity["value"] = "";
						
						if to_scene["value"] == "":
							imgui.text("Unlinked");
						elif to_entity["value"] == "":
							imgui.text(f"Linked to scene {to_scene["value"]}");
						else:
							imgui.text(f"Linked to {to_scene["value"]}.{to_entity["value"]}");
						
						imgui.same_line();
						if imgui.button("Browse"):
							self.selector = DoorEditor.Selector(self, door);
						
						orientation = get_script_data(door.entity, "orientation");
						orientation["value"] = eegui_input_orientation("Orientation", orientation["value"]);
						
						imgui.tree_pop();		

		if self.selector != None:
			self.selector.draw();
			if not self.selector.open:
				self.selector = None;

	def draw_canvas(self):
		for scene in self.door_hierarchy:
			if scene == self.parent.scene["name"]:
				for door in self.door_hierarchy[scene]:
					door_gizmo = SpriteBank.search("editor_door");
					x, y = door.entity["position"];

					prototype = AssetManager.search("prototype", door.entity["prototype"]);
					box = next((x for x in prototype["boxes"] if x["type"] == "trigger"), None);
					if box != None:
						x0, y0, x1, y1 = box["aabb"];
						w, h = x1-x0, y1-y0;
						x = x + x0 + w/2;
						y = y + y1;
					
					idx = 0;
					if door.points_to() and not door.is_pointed_to():
						idx = 1;
					if door.is_pointed_to() and not door.points_to():
						idx = 2;
					if door.points_to() and door.is_pointed_to():
						idx = 3;
					self.parent.canvas.draw_image(x-door_gizmo.frame_width/2, y-door_gizmo.frame_height, door_gizmo.frame_images[idx]);

					arrow_gizmo = SpriteBank.search("editor_arrow");
					orientation = get_script_data(door.entity, "orientation");
					x_off = -arrow_gizmo.frame_width/2;
					y_off = -door_gizmo.frame_height/2-arrow_gizmo.frame_height/2;
					match orientation["value"]:
						case 1:
							x_off += door_gizmo.frame_width/2+arrow_gizmo.frame_width/2;
						case 2:
							y_off -= door_gizmo.frame_height/2+arrow_gizmo.frame_height/2;
						case 3:
							x_off -= door_gizmo.frame_width/2+arrow_gizmo.frame_width/2;
						case 4:
							y_off += door_gizmo.frame_height/2+arrow_gizmo.frame_height/2;
					self.parent.canvas.draw_image(x+x_off, y+y_off, arrow_gizmo.frame_images[orientation["value"]], c=(255, 128, 0));

class SceneViewer:
	def __init__(self, parent):
		self.parent = parent;

		self.show_tiles = True;
		self.show_entities = True;
		self.show_texts = True;

		self.show_grid = False;
		self.show_walls = True;
		self.show_boxes = False;
		self.show_gizmos = True;

	def draw_tiles(self):
		tilemap = self.parent.scene["tilemap"];
		palette = SpriteBank.search(tilemap["palette"]);

		match tilemap["type"]:
			case "sparse":
				for tile in tilemap["sparse"]:
					frame_idx = clamp(tile["frame_idx"], 0, palette.frame_count-1);
					self.parent.canvas.draw_image(
						tile["position"][0], tile["position"][1],
						palette.frame_images[frame_idx]
					);

				if self.parent.edit_mode == EditMode.TILEMAP:
					cursor = self.parent.canvas_io.get_cursor();
					grid_cursor = self.parent.canvas_grid.snap_point(cursor);
					x0, y0 = grid_cursor;
					x1, y1 = x0+16, y0+16;
					self.parent.canvas.draw_aabb(
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
							frame_idx = clamp(frame_idx, 0, palette.frame_count-1);
							self.parent.canvas.draw_image(
								x, y,
								palette.frame_images[frame_idx]
							);
	
	def draw_entities(self):
		def sort_y(entity):
			base_y = get_entity_aabb(entity)[3];
			prototype = AssetManager.search("prototype", entity["prototype"]);
			y_offset = prototype["y_sort_offset"] if prototype != None else 0;
			return base_y+y_offset;
		y_sorted = self.parent.scene["entities"];
		y_sorted = sorted(y_sorted, key=lambda x: x["layer"]);
		y_sorted = sorted(y_sorted, key=sort_y);

		for entity in y_sorted:
			prototype = AssetManager.search("prototype", entity["prototype"]);
			sprite = SpriteBank.search(prototype["sprite"], safe=False) if prototype != None else None;
			aabb = get_entity_aabb(entity);
			
			if sprite != None:
				x, y = entity["position"];
				frame_idx = clamp(entity["frame_idx"], 0, sprite.frame_count-1);
				self.parent.canvas.draw_image(x, y, sprite.frame_images[frame_idx]);
			else:
				self.parent.canvas.draw_aabb(aabb, (255, 255, 0));

			if prototype != None and self.show_boxes:
				for box in prototype["boxes"]:
					colour = (255, 0, 0) if box["type"] == "blocker" else (0, 255, 0);
					x0, y0, x1, y1 = box["aabb"];
					x0, y0, x1, y1 = x0+x, y0+y, x1+x, y1+y;
					self.parent.canvas.draw_aabb((x0, y0, x1, y1), colour);

			if self.parent.selection_context.is_selected(entity):
				self.parent.canvas.draw_aabb(aabb, (255, 255, 255));
	
	def draw_texts(self):
		for text in self.parent.scene["texts"]:
			self.parent.canvas.draw_text(text["position"], text["text"], 8*text["scale"], text["colour"]);
			self.parent.canvas.draw_aabb(get_text_aabb(text), (255, 255, 255));
	
	def draw_walls(self):
		if self.parent.scene["has_bounds"]:
			self.parent.canvas.draw_aabb(self.parent.scene["bounds"], (128, 0, 0), False);
		
		for wall in self.parent.scene["walls"]:
			colour = (255, 255, 0) if self.parent.wall_editor._is_selected(wall) else (255, 0, 0);
			if wall["type"] == "aabb":
				self.parent.canvas.draw_aabb(wall["aabb"], colour, False);
			elif wall["type"] == "segment":
				(x0, y0), (x1, y1) = wall["segment"];
				self.parent.canvas.draw_line(x0, y0, x1, y1, colour);		
				self.parent.canvas.draw_circle(x0, y0, 2, colour);
				self.parent.canvas.draw_circle(x1, y1, 2, colour);
	
	def draw(self):
		self.parent.canvas.clear(tuple(self.parent.scene["background"]));

		if self.show_tiles:
			self.draw_tiles();
		if self.show_grid:
			self.parent.canvas_grid.draw_lines((64, 64, 64));
		
		if self.show_entities:
			self.draw_entities();
		if self.show_texts:
			self.draw_texts();
		if self.show_walls:
			self.draw_walls();	

		if self.show_gizmos:
			self.parent.door_editor.draw_canvas();

class SceneEditor:
	def _load_scene(self, scene):		
		self.scene = scene;

		self.event_queue.clear();
		self.canvas_manip.clear();
		self.manip_registry.clear();

		self.selection_context.clear();
		
		self.tilemap_editor.on_load_scene();
		self.wall_editor.on_load_scene();
		self.text_editor.on_load_scene();

	def _is_scene_loaded(self):
		return self.scene in AssetManager.get_all("scene");

	def __init__(self):
		self.canvas_size = (1000, 720);
		self.canvas = Canvas(self.canvas_size[0], self.canvas_size[1], origin=(self.canvas_size[0]//2, self.canvas_size[1]//2));
		self.canvas_io = CanvasIO(self.canvas);
		self.canvas_grid = CanvasGrid(
			self.canvas,
			16
		);

		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(self.canvas_io, self.event_queue);
		self.manip_registry = CanvasManipRegistry();

		self.selection_context = SelectionContext();
		self.clipboard = Clipboard();
		self.trash = Trash(deferred=True);

		self.edit_mode = EditMode.ENTITIES;
		self.snap = True;

		self.tilemap_editor = TilemapEditor(self);
		self.wall_editor = WallEditor(self);
		self.text_editor = TextEditor(self);
		self.scene_viewer = SceneViewer(self);
		self.door_editor = DoorEditor(self);

		self._load_scene(AssetManager.get_first("scene"));
	
	def view_drag_handler(self, event):
		match event.signal:
			case CanvasManipDrag.Signal.TICK:
				x0, y0 = event.start;
				x, y = event.point;
				dx, dy = x-x0, y-y0;
				
				ox, oy = self.canvas.origin;
				self.canvas.origin = ox+dx, oy+dy;

	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CanvasManipClick):
				if event.eeid == None:
					self.selection_context.clear();
				else:
					entity = self.manip_registry.search(event.eeid);
					self.selection_context.select(entity, exclusive=True);
			
			if isinstance(event, CanvasManipDrag):
				if event.eeid != None:
					match event.signal:
						case CanvasManipDrag.Signal.TICK:
							entity = self.selection_context.get_selection(single=True);
							point = event.point;
							delta = event.delta;
							position = point[0]+delta[0], point[1]+delta[1];
							if self.snap:
								position = self.canvas_grid.snap_point(position);
							entity["position"] = position;
				else:
					self.view_drag_handler(event);
	
	def get_entity_sprite(self, entity):
		prototype = AssetManager.search("prototype", entity["prototype"]);
		return SpriteBank.search(prototype["sprite"] if prototype != None else "null");

	def get_entity_script_data_signatures(self, entity):
		script_data = [];
		prototype = AssetManager.search("prototype", entity["prototype"]);
		if prototype != None:
			for script_name in prototype["scripts"]:
				script = AssetManager.search("script", script_name);
				script_data += script["script_data"];
		return script_data;

	def rectify_script_data(self):
		for entity in self.scene["entities"]:
			signatures = self.get_entity_script_data_signatures(entity);

			# Remove invalid keys and types
			trash = [];
			for data in entity["script_data"]:
				match = next(
					(x for x in signatures if x["key"] == data["key"] and x["type"] == data["type"]), 
					None
				);
				if match == None:
					trash.append(data);
			process_trash(entity["script_data"], trash);
		
			# Deduplicate
			first = {}
			for i, data in enumerate(entity["script_data"]):
				first[data["key"]] = i;
			trash = [];
			for i, data in enumerate(entity["script_data"]):
				if first[data["key"]] != i:
					trash.append(data);
			process_trash(entity["script_data"], trash);

			def make_value(type):
				match type:
					case "vec2": return [0, 0];
					case _: return ee_types.construct_type(signature["type"]).prototype();
		
			# Add missing signatures
			for signature in signatures:
				match = next(
					(x for x in entity["script_data"] if x["key"] == signature["key"] and x["type"] == signature["type"]), 
					None
				);
				if match == None:
					entity["script_data"].append({
						"key": signature["key"],
						"type": signature["type"],
						"value": make_value(signature["type"])
					});
	
	def synchronize_manip(self):
		def make_shape(entity):
			aabb = get_entity_aabb(entity);
			return CanvasManipRect(aabb);
		shapes = [make_shape(x) for x in self.scene["entities"]];
		
		self.manip_registry.update(self.scene["entities"], shapes);
		self.canvas_manip.synchronize(self.manip_registry);
	
	def draw_menu_bar(self):
		if imgui.begin_menu_bar():

			if imgui.begin_menu("Scene"):
				if imgui.begin_menu("Open"):
					scenes = AssetManager.get_all("scene");
					scene_last = self.scene;
					for scene in scenes:
						if imgui.menu_item_simple(scene["name"]):
							self.scene = scene;
					if self.scene != scene_last:
						self._load_scene(self.scene);
					imgui.end_menu();
				imgui.end_menu();
			
			if imgui.begin_menu("View"):
				_, self.scene_viewer.show_tiles = imgui.menu_item("Tiles", "", self.scene_viewer.show_tiles);
				_, self.scene_viewer.show_entities = imgui.menu_item("Entities", "", self.scene_viewer.show_entities);
				_, self.scene_viewer.show_texts = imgui.menu_item("Texts", "", self.scene_viewer.show_texts);
				_, self.scene_viewer.show_boxes = imgui.menu_item("Boxes", "", self.scene_viewer.show_boxes);
				_, self.scene_viewer.show_walls = imgui.menu_item("Walls", "", self.scene_viewer.show_walls);
				_, self.scene_viewer.show_gizmos = imgui.menu_item("Gizmos", "", self.scene_viewer.show_gizmos);
				_, self.scene_viewer.show_grid = imgui.menu_item("Grid", "", self.scene_viewer.show_grid);
				imgui.end_menu();
			
			if imgui.begin_menu("Grid"):
				imgui.set_next_item_width(64);
				self.canvas_grid.size = eegui_input_int("Size", self.canvas_grid.size, style=EEGUIIntStyle.SLIDER, low_bound=2, high_bound=16);
				self.snap = eegui_input_bool("Snap", self.snap);
				imgui.end_menu();
			
			imgui.end_menu_bar();		
	
	def gui_draw_entities(self):	
		for entity in self.scene["entities"]:
			name = entity["name"] if len(entity["name"]) > 0 else str(id(entity));
			sprite = self.get_entity_sprite(entity);

			imgui.set_next_item_open(self.selection_context.is_selected(entity));
			node_open = imgui.tree_node(f"{name}####{id(entity)}");

			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("Delete"):
					self.trash.trash_item(self.scene["entities"], entity);
					imgui.close_current_popup();
				imgui.end_popup();
			
			if node_open:
				self.selection_context.select(entity, exclusive=True);
				
				entity["name"] = eegui_input_string("Name", entity["name"]);
				entity["prototype"] = eegui_input_asset("Prototype", entity["prototype"], "prototype");
				if len(entity["prototype"]) > 0 and len(entity["name"]) <= 0:
					entity["name"] = entity["prototype"];

				entity["frame_idx"] = eegui_input_int("Frame", entity["frame_idx"], EEGUIIntStyle.SLIDER, 0, sprite.frame_count-1);
				entity["layer"] = eegui_input_int("Layer", entity["layer"], 0, 255);
				
				if imgui.tree_node("Script data"):
					for data in entity["script_data"]:
						if imgui.tree_node(f"{data["key"]}####{id(data)}"):
							data_type = ee_types.TypeRegistry.get(data["type"]);
							data["value"] = eegui_typed_input(data["key"], data_type, data["value"]);
							imgui.tree_pop();
					imgui.tree_pop();
				imgui.tree_pop();
	
	def gui_draw_properties_editor(self):
		self.scene["has_background"] = eegui_input_bool("Has background", self.scene["has_background"]);
		if self.scene["has_background"]:
			self.scene["background"] = eegui_input_colour("Background", self.scene["background"]);
		self.scene["has_bounds"] = eegui_input_bool("Has bounds", self.scene["has_bounds"]);
		if self.scene["has_bounds"]:
			self.scene["bounds"] = eegui_input_aabb("Bounds", self.scene["bounds"]);
		self.scene["free_camera"] = eegui_input_bool("Free camera", self.scene["free_camera"]);
	
	def scene_context_menu(self):
		selection = self.selection_context.get_selection(single=True);
		hovered = selection != None and aabb_contains_point(self.canvas_io.get_cursor(), get_entity_aabb(selection));
		if hovered:
			if imgui.menu_item_simple("Delete"):
				self.trash.trash_item(self.scene["entities"], selection);
		
		if imgui.menu_item_simple("Spawn"):
			entity = AssetManager.get_document("scene").type_helper.search("entities").T.get_inmost_type().prototype();
			entity["name"] = "New entity";
			entity["position"] = self.canvas_io.get_cursor();
			self.scene["entities"].append(entity);

	def draw(self):
		self.draw_menu_bar();

		if not self._is_scene_loaded():
			return;

		self.canvas_io.tick();
		self.synchronize_manip();
		self.rectify_script_data();

		def run_left_panel(panel_tick):
			imgui.begin_child(
				"left-panel",
				imgui.ImVec2((imgui.get_content_region_avail().x - self.canvas.width) * 0.9, imgui.get_content_region_avail().y),
				0, 0
			);
			panel_tick();
			imgui.end_child();
		
		def entities_tick():
			if InputManager.is_command(glfw.KEY_C):
				self.clipboard.copy(self.selection_context.get_selection(single=True), copy_mode=Clipboard.CopyMode.DEEP, exclusive=True);
			if InputManager.is_command(glfw.KEY_V):
				self.clipboard.paste(self.scene["entities"]);
			
			if InputManager.is_command(glfw.KEY_D):
				selection = self.selection_context.get_selection(single=True);
				if selection != None:
					self.trash.trash_item(self.scene["entities"], selection);
			if InputManager.is_command(glfw.KEY_Z):
				self.trash.restore();
			
			self.canvas_manip.tick();
			self.handle_events();

			self.gui_draw_entities();
			self.trash.flush();

		def tilemap_tick():
			self.tilemap_editor.tick();
			self.tilemap_editor.draw_gui();
		
		def walls_tick():
			self.wall_editor.tick();
			self.wall_editor.draw_gui();
		
		def doors_tick():
			self.door_editor.logic();
			self.door_editor.draw_gui();
		
		def texts_tick():
			self.text_editor.tick();
			self.text_editor.draw_gui();
		
		def properties_tick():
			self.gui_draw_properties_editor();
		
		match self.edit_mode:
			case EditMode.ENTITIES:
				run_left_panel(entities_tick);
			case EditMode.TILEMAP:
				run_left_panel(tilemap_tick);
			case EditMode.WALLS:
				run_left_panel(walls_tick);
			case EditMode.DOORS:
				run_left_panel(doors_tick);
			case EditMode.TEXTS:
				run_left_panel(texts_tick);
			case EditMode.PROPERTIES:
				run_left_panel(properties_tick);	

		imgui.same_line();
		imgui.begin_child(
			"main-panel",
			imgui.ImVec2(imgui.get_content_region_avail().x, imgui.get_content_region_avail().y),
			0, 0
		);

		if imgui.begin_tab_bar("edit-mode"):
			for value in EditMode:
				tab_visible, tab_open = imgui.begin_tab_item(value.name);
				if tab_visible:
					self.edit_mode = value;
					imgui.end_tab_item();
			imgui.end_tab_bar();

		self.scene_viewer.draw();
		self.canvas.render(gui_id="canvas");
		if EEGUIContextMenu.begin("canvas"):
			self.scene_context_menu();
			imgui.end_popup();
		
		imgui.end_child();
		