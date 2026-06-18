from imgui_bundle import imgui;
import glfw;
import csv;

from ee_cowtools import *;
from ee_canvas import *;
from ee_assets import *;
from ee_sprites import SpriteBank, EditorSprite, SpritePreview;
from ee_input import InputManager;
from ee_imgui import *;

#########################################################
## SCENE EDITOR

class EditMode(Enum):
	ENTITIES = 0,
	TILEMAP = 1,
	WALLS = 2,
	TEXTS = 3,
	PROPERTIES = 4

class CanvasConfig:
	def __init__(self):
		self.show_entities = True;
		self.show_tiles = True;
		self.show_texts = True;

		self.show_grid = False;
		self.show_walls = True;
		self.show_boxes = False;

		self.snap_to_grid = True;

class CreateEntityEvent:
	def __init__(self, entity):
		self.entity = entity;
class DeleteEntityEvent:
	def __init__(self, entity):
		self.entity = entity;

class CreateTileEvent:
	def __init__(self, position, frame_idx):
		self.position = position;
		self.frame_idx = frame_idx;
class DeleteTileEvent:
	def __init__(self, tile):
		self.tile = tile;

class CreateWallEvent:
	def __init__(self, wall):
		self.wall = wall;
class DeleteWallEvent:
	def __init__(self, wall):
		self.wall = wall;

class UndoEvent:
	def __init__(self):
		pass;

class CreateTextEvent:
	def __init__(self, text):
		self.text = text;
class DeleteTextEvent:
	def __init__(self, text):
		self.text = text;

class TilemapEditor:
	def __init__(self, parent):
		self.parent = parent;
		self.tilemap = None;
		self.selected_frame = 0;
		self.event_queue = [];
	
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

	def _clean(self):
		match self._type():
			case "sparse":
				for tile in self._data():
					if not self._spatial_search(tile["position"]) is tile:
						self.parent.event_queue.append(DeleteTileEvent(tile));
	
	def on_load_scene(self):
		if self.tilemap != None:
			self._clean();
		self.tilemap = self.parent.scene["tilemap"];
		self.event_queue.clear();
	
	def gui_draw_palette(self):
		if self.tilemap == None:
			return;
	
		self.tilemap["palette"] = imgui_asset_name_selector("palette", "sprite", self.tilemap["palette"]);
		if self.tilemap["palette"] == "":
			return;

		match self._type():
			case "sparse":
				sprite = SpriteBank.get(self.tilemap["palette"]);
				wdw_w = imgui.get_content_region_avail().x;
				cols = int(wdw_w // 72);
				rows = int(math.ceil(sprite.frame_count / cols));

				i = 0;
				for r in range(rows):
					for c in range(cols):
						if i < sprite.frame_count:
							tint = (0.5, 0.5, 0.5, 1) if i == self.selected_frame else (1, 1, 1, 1);
							if imgui.image_button(f"##{id(i)}", imgui.ImTextureRef(sprite.frame_textures[i]), (64, 64), tint_col=tint):
								self.selected_frame = i;
							imgui.same_line();
						i += 1;
					imgui.new_line();
			case "dense":
				explorer = ToolWindowRegistry.lookup(FileExplorer);
				if imgui.button(f"...") and not explorer.is_open():
					explorer.open();
					explorer.get().configure(self._data()["csv"], "assets", "*.csv");
				if explorer.is_open() and explorer.get().is_targeting(self._data()["csv"]):
					harvest = explorer.get_result();
					if harvest != None:
						self._data()["csv"] = str(Path("assets")/harvest);
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
				
				_, self._data()["position"] = imgui.input_int2("Position", self._data()["position"]);
	
	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CreateTileEvent):
				self.tilemap["sparse"].append(
					{
						"position": list(event.position),
						"frame_idx": event.frame_idx
					}
				);
			if isinstance(event, DeleteTileEvent):
				self.tilemap["sparse"].remove(event.tile);
	
	def tick_sparse(self):
		palette = SpriteBank.get(self.tilemap["palette"]);
		self.selected_frame = clamp(self.selected_frame, 0, palette.frame_count-1);

		if self.parent.canvas_io.cursor_in_bounds():
			if InputManager.is_held(glfw.MOUSE_BUTTON_LEFT):
				cursor = self.parent.canvas_io.get_cursor();
				tile_cursor = self.parent.canvas_grid.snap_point(cursor);
				if InputManager.is_held(glfw.KEY_LEFT_SHIFT):
					for idx, tile in enumerate(self.tilemap["sparse"]):
						tx, ty = self.parent.canvas_grid.snap_point(tile["position"]);
						cx, cy = tile_cursor;
						if int(tx) == int(cx) and int(ty) == int(cy):
							self.event_queue.append(DeleteTileEvent(self.tilemap["sparse"][idx]));
				elif self.selected_frame != None:
					existing = self._spatial_search(tile_cursor);
					if existing == None:
						self.event_queue.append(CreateTileEvent(tile_cursor, self.selected_frame));
					else:
						existing["frame_idx"] = self.selected_frame;

	def tick(self):
		if self.tilemap == None:
			return;
		if self.tilemap["palette"] == "":
			return;

		match self._type():
			case "sparse":
				self.tick_sparse();
	
		self.handle_events();

	def __del__(self):
		if self.tilemap != None:
			self._clean();

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
		self.manip_map = {};
		self.context = {};
	
		self.place_mode = WallEditor.PlaceModes.NONE;
		self.selected = None;

	def on_load_scene(self):
		self.walls = self.parent.scene["walls"];
		self.canvas_manip.clear();
		self.manip_map.clear();
		self.event_queue.clear();
		self.context.clear();
	
	def gui_draw_walls(self):
		if self.walls == None:
			return;

		imgui.text("Place mode");
		imgui.same_line();
		self.place_mode = imgui_enum_selector("place-mode", self.PlaceModes, self.place_mode);

		for idx, wall in enumerate(self.walls):
			imgui.set_next_item_open(wall == self.selected);
			node_open = imgui.tree_node(f"{idx}##{id(self.walls)}{idx}");

			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("Delete"):
					self.event_queue.append(DeleteWallEvent(wall));
					imgui.close_current_popup();
				if imgui.menu_item_simple("Duplicate"):
					self.event_queue.append(CreateWallEvent(list(wall)));
					imgui.close_current_popup();
				imgui.end_popup();

			if node_open:
				match wall["type"]:
					case "aabb":
						wall["aabb"] = list(wall["aabb"]);
						lstapply(wall["aabb"], int);
						_, self.walls[idx]["aabb"] = imgui.input_int4("AABB", self.walls[idx]["aabb"]);
					case "segment":
						wall["segment"][0] = list(wall["segment"][0]);
						wall["segment"][1] = list(wall["segment"][1]);
						lstapply(wall["segment"][0], int);
						lstapply(wall["segment"][1], int);
						_, self.walls[idx]["segment"][0] = imgui.input_int2("A", self.walls[idx]["segment"][0]);
						_, self.walls[idx]["segment"][1] = imgui.input_int2("B", self.walls[idx]["segment"][1]);
				imgui.tree_pop();

	def is_selected(self, wall):
		return self.selected == wall;	
	
	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CreateWallEvent):
				self.walls.append(event.wall);
			if isinstance(event, DeleteWallEvent):
				eeid = None;
				for k,v in self.manip_map.items():
					if v == event.wall:
						eeid = k;
				del self.manip_map[eeid];
				self.canvas_manip.delete_shape(eeid);
				self.walls.remove(event.wall);

			if isinstance(event, CanvasManipClick):
				hit = event.eeid != None;

				if hit:
					self.selected = self.manip_map[event.eeid];
				else:
					self.selected = None;
				
				if self.place_mode != None and not hit and not InputManager.is_held(glfw.KEY_LEFT_SHIFT):
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
				else:
					match event.signal:
						case CanvasManipDrag.Signal.START:
							wall = self.manip_map[event.eeid];
							self.context["type"] = wall["type"];
							x, y = event.point;

							match wall["type"]:
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
							wall = self.manip_map[event.eeid];
							type = self.context["type"];

							match type:
								case "aabb":
									if self.context["inside"]:
										point = event.point[0] + self.context["delta"][0], event.point[1] + self.context["delta"][1];
										point = self.parent.canvas_grid.snap_point(point);
										lstcopy(wall["aabb"], relocate_aabb(wall["aabb"], point));
									else:
										point = self.parent.canvas_grid.snap_point(event.point);
										lstcopy(wall["aabb"], shape_aabb(wall["aabb"], self.context["edge"], point));
								case "segment":
									if self.context["inside"]:
										point = event.point[0] + self.context["delta"][0], event.point[1] + self.context["delta"][1];
										point = self.parent.canvas_grid.snap_point(point);
										lstcopy(wall["segment"], relocate_segment(wall["segment"], point));
									else:
										point = self.parent.canvas_grid.snap_point(event.point);
										lstcopy(wall["segment"], shape_segment(wall["segment"], self.context["end"], point));
	
	def tick(self):
		if self.walls == None:
			return;
	
		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_D):
			if self.selected != None:
				self.event_queue.append(DeleteWallEvent(self.selected));
				self.selected = None;
	
		for wall in self.walls:
			if not wall in self.manip_map.values():
				match wall["type"]:
					case "aabb":
						eeid = self.canvas_manip.register_aabb(wall["aabb"]);
					case "segment":
						eeid = self.canvas_manip.register_segment(wall["segment"]);
				self.manip_map[eeid] = wall;
		
		for k,v in self.manip_map.items():
			shape = self.canvas_manip.get_shape(k);
			shape.update(v[v["type"]]);
		
		self.canvas_manip.tick();
		self.handle_events();

class TextEditor:
	def __init__(self, parent):
		self.parent = parent;
		self.texts = None;

		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(self.parent.canvas_io, self.event_queue);
		self.manip_map = {};
		self.context = {};

	def on_load_scene(self):
		self.texts = self.parent.scene["texts"];
		self.canvas_manip.clear();
		self.manip_map.clear();
		self.event_queue.clear();
		self.context.clear();
	
	def gui_draw_texts(self):
		if self.texts == None:
			return;
	
		node_open = imgui.tree_node(f"Texts##{id(self.texts)}");

		if imgui.begin_popup_context_item():
			if imgui.menu_item_simple("New text"):
				self.event_queue.append(CreateTextEvent({
					"text": "Hello, world!",
					"colour": [255, 255, 255],
					"scale": 1,
					"position": [0, 0]
				}));
				imgui.close_current_popup();
			imgui.end_popup();

		if node_open:
			for idx, text in enumerate(self.texts):
				node_open = imgui.tree_node(f"{idx}##{id(self.texts)}{idx}");

				if imgui.begin_popup_context_item():
					if imgui.menu_item_simple("Delete"):
						self.event_queue.append(DeleteTextEvent(text));
						imgui.close_current_popup();
					imgui.end_popup();

				if node_open:
					_, text["text"] = imgui.input_text("Text", text["text"]);

					r, g, b = text["colour"];
					_, (r, g, b) = imgui.color_edit3("Colour", (r/255, g/255, b/255));
					text["colour"] = [int(r*255), int(g*255), int(b*255)];

					_, text["scale"] = imgui.input_int("Scale", text["scale"], 0, 3);

					_, text["position"] = imgui.input_int2("Position", text["position"]);
					imgui.tree_pop();
			imgui.tree_pop();
	
	def move_text(self, text, point):
		x, y = point;
		text["position"][0] = int(x);
		text["position"][1] = int(y);
	
	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CreateTextEvent):
				self.texts.append(event.text);
			if isinstance(event, DeleteTextEvent):
				self.texts.remove(event.text)

			if isinstance(event, CanvasManipDrag):
				if event.eeid != None:
					match event.signal:
						case CanvasManipDrag.Signal.START:
							text = self.manip_map[event.eeid];
							self.context = {
								"delta": (text["position"][0] - event.point[0], text["position"][1] - event.point[1]),
							}
						case CanvasManipDrag.Signal.TICK:
							text = self.manip_map[event.eeid];
							point = event.point[0] + self.context["delta"][0], event.point[1] + self.context["delta"][1];
							point = self.parent.canvas_grid.snap_point(point);
							self.move_text(text, point);
	
	def get_text_aabb(self, text):
		x0, y0 = text["position"];
		width = len(text["text"]) * 8 * text["scale"];
		x1, y1 = x0 + width, y0 + 8 * text["scale"];
		return (x0, y0, x1, y1);
	
	def tick(self):
		if self.texts == None:
			return;
	
		for text in self.texts:
			if not text in self.manip_map.values():
				eeid = self.canvas_manip.register_aabb(self.get_text_aabb(text));
				self.manip_map[eeid] = text;
		for k,v in self.manip_map.items():
			shape = self.canvas_manip.get_shape(k);
			shape.update(self.get_text_aabb(v));
		
		self.canvas_manip.tick();
		self.handle_events();

class SceneEditor:
	def _load_scene(self, scene):		
		self.scene = scene;

		self.event_queue.clear();
		self.selection_context.clear();
		self.canvas_manip.clear();
		self.manip_map.clear();
		
		self.tilemap_editor.on_load_scene();
		self.wall_editor.on_load_scene();
		self.text_editor.on_load_scene();

	def _is_scene_loaded(self):
		return self.scene in AssetManager.get_assets("scene");

	def __init__(self):
		self.canvas_size = (1000, 720);
		self.tile_size = 16;
		self.canvas = Canvas(self.canvas_size[0], self.canvas_size[1], origin=(self.canvas_size[0]//2, self.canvas_size[1]//2));
		self.canvas_io = CanvasIO(self.canvas);
		self.canvas_grid = CanvasGrid(
			self.canvas,
			self.tile_size
		);

		self.event_queue = [];
		self.selection_context = {};
		self.clipboard = [];
		self.trash = [];

		self.canvas_manip = CanvasManipulator(self.canvas_io, self.event_queue);
		self.manip_map = {};

		self.tilemap_editor = TilemapEditor(self);
		self.wall_editor = WallEditor(self);
		self.text_editor = TextEditor(self);

		self.canvas_config = CanvasConfig();
		self.edit_mode = EditMode.ENTITIES;

		self._load_scene(AssetManager.get_first("scene"));
	
	def view_drag_handler(self, event):
		match event.signal:
			case CanvasManipDrag.Signal.START:
				self.selection_context["origin"] = self.canvas.origin;
				x, y = event.point;
				self.selection_context["point"] = self.canvas._transform(x, y);
			case CanvasManipDrag.Signal.TICK:
				ox, oy = self.selection_context["origin"];
				x0, y0 = self.selection_context["point"];

				x1, y1 = event.point;
				x1, y1 =  self.canvas._transform(x1, y1);
				dx, dy = x1-x0, y1-y0;
				self.canvas.origin = ox+dx, oy+dy;
				
				self.selection_context["origin"] = self.canvas.origin;
				self.selection_context["point"] = x1, y1;

	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CanvasManipClick):
				if event.eeid == None:
					self.selection_context = {};
				else:
					self.selection_context["entity"] = self.manip_map[event.eeid];
			
			if isinstance(event, CanvasManipDrag):
				if event.eeid != None:
					match event.signal:
						case CanvasManipDrag.Signal.START:
							entity = self.manip_map[event.eeid];
							delta = entity["position"][0] - event.point[0], entity["position"][1] - event.point[1];
							self.select_entity(entity);
							self.selection_context["delta"] = delta;
						case CanvasManipDrag.Signal.TICK:
							entity = self.selection_context["entity"];
							point = event.point;
							delta = self.selection_context["delta"];
							position = point[0] + delta[0], point[1] + delta[1];
							if self.canvas_config.snap_to_grid:
								position = self.canvas_grid.snap_point(position);
							entity["position"] = position;
				else:
					self.view_drag_handler(event);
			
			if isinstance(event, CreateEntityEvent):
				self.scene["entities"].append(event.entity);
				self.select_entity(event.entity);
			
			if isinstance(event, DeleteEntityEvent):
				if self.get_selected_entity() == event.entity:
					self.select_entity(None);
				self.trash.append(event.entity);
				self.scene["entities"].remove(event.entity);
	
	def get_entity_sprite(self, entity):
		prototype = AssetManager.search("prototype", entity["prototype"]);
		return SpriteBank.get(prototype["sprite"] if prototype != None else "null");

	def get_entity_aabb(self, entity):
		sprite = self.get_entity_sprite(entity);
		x0, y0 = entity["position"];
		x1, y1 = x0 + sprite.frame_width, y0 + sprite.frame_height;
		return (x0, y0, x1, y1);

	def get_entity_script_data_signatures(self, entity):
		script_data = [];
		prototype = AssetManager.search("prototype", entity["prototype"]);
		if prototype != None:
			for script_name in prototype["scripts"]:
				script = AssetManager.search("script", script_name);
				script_data += script["script_data"];
		return script_data;

	def rectify_entity_script_data(self, entity):
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

	def select_entity(self, entity):
		if entity == None:
			self.selection_context = {};
		else:
			self.selection_context = { "entity": entity };

	def get_selected_entity(self):
		return None if not "entity" in self.selection_context else self.selection_context["entity"];
	
	def manip_bookkeeping_tick(self):
		for entity in self.scene["entities"]:
			if entity not in self.manip_map.values():
				aabb = self.get_entity_aabb(entity);
				eeid = self.canvas_manip.register_aabb(aabb);
				self.manip_map[eeid] = entity
		for k,v in self.manip_map.items():
			aabb = self.get_entity_aabb(v);
			shape = self.canvas_manip.get_shape(k);
			shape.update(aabb);
	
	def copypaste_tick(self):
		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_C):
			if "entity" in self.selection_context:
				self.clipboard = [self.selection_context["entity"]];
		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_V):
			for entity in self.clipboard:
				self.event_queue.append(CreateEntityEvent(copy.deepcopy(entity)));
	
	def undo_tick(self):
		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_Z):
			if len(self.trash) > 0:
				restore = self.trash.pop();
				CreateEntityEvent(restore);
	
	def gui_draw_scene_selector(self):
		scene_last = self.scene;
		self.scene = imgui_asset_selector(id(self.scene), "scene", self.scene);
		if self.scene != scene_last:
			self._load_scene(self.scene);
	
	def gui_draw_entity(self, entity):
		name = entity["name"] if len(entity["name"]) > 0 else str(id(entity));
		prototype = AssetManager.search("prototype", entity["prototype"]);
		sprite = self.get_entity_sprite(entity);

		selected = entity == self.get_selected_entity();
		imgui.set_next_item_open(selected);
		node_open = imgui.tree_node(f"{name}####{id(entity)}");

		if imgui.begin_popup_context_item():
			if imgui.menu_item_simple("Delete"):
				self.event_queue.append(DeleteEntityEvent(entity));
				imgui.close_current_popup();
			imgui.end_popup();
		
		if node_open:
			if not selected:
				self.select_entity(entity);
			
			_, entity["name"] = imgui.input_text("Name", entity["name"]);
			entity["prototype"] = imgui_asset_input("prototype", "prototype", entity["prototype"]);

			if len(entity["prototype"]) > 0 and len(entity["name"]) <= 0:
				entity["name"] = entity["prototype"];

			_, entity["frame_idx"] = imgui.slider_int("Frame", entity["frame_idx"], 0, sprite.frame_count-1);
			
			_, entity["layer"] = imgui.input_int("Layer", entity["layer"], 0, 255);
			
			if imgui.tree_node("Script data"):
				self.rectify_entity_script_data(entity);
				for data in entity["script_data"]:
					if imgui.tree_node(f"{data["key"]}####{id(data)}"):
						match data["type"]:
							case "bool":
								_, data["value"] = imgui.checkbox(data["key"], data["value"]);
							case "int":
								_, data["value"] = imgui.input_int(data["key"], data["value"]);
							case "string":
								_, data["value"] = imgui.input_text(data["key"], data["value"]);
							case "vec2":
								_, data["value"] = imgui.input_int2(data["key"], data["value"]);
							case _:
								if AssetManager.has_type(data["type"]):
									data["value"] = imgui_asset_input("value", data["type"], data["value"]);
								else:
									_, data["value"] = imgui.input_text("value", data["value"]);						
						imgui.tree_pop();
				imgui.tree_pop();
			imgui.tree_pop();
	
	def gui_draw_entities(self):
		node_open = imgui.tree_node("Entities");
		if imgui.begin_popup_context_item("Create"):
			if imgui.menu_item_simple("New entity"):
				entity = {
						"name": "",
						"prototype": "",
						"position": [0, 0],
						"frame_idx": 0,
						"layer": 0,
						"script_data": []
				};
				self.event_queue.append(CreateEntityEvent(entity));
				imgui.close_current_popup();
			imgui.end_popup();
		
		if node_open:
			for entity in self.scene["entities"]:
				self.gui_draw_entity(entity);
			imgui.tree_pop();
	
	def gui_draw_properties_editor(self):
		_, self.scene["has_background"] = imgui.checkbox("Has background", self.scene["has_background"]);
		if self.scene["has_background"]:
			r, g, b = self.scene["background"];
			_, (r, g, b) = imgui.color_edit3("Background", (r/255, g/255, b/255));
			self.scene["background"] = [int(r*255), int(g*255), int(b*255)];

		_, self.scene["has_bounds"] = imgui.checkbox("Has bounds", self.scene["has_bounds"]);
		if self.scene["has_bounds"]:
			_, self.scene["bounds"] = imgui.input_int4("Bounds", self.scene["bounds"]);
	
	def canvas_draw_entity(self, entity):
		x, y = entity["position"];
		sprite = self.get_entity_sprite(entity);
		frame_idx = clamp(entity["frame_idx"], 0, sprite.frame_count-1);
		self.canvas.draw_image(x, y, sprite.frame_images[frame_idx]);

		if self.canvas_config.show_boxes:
			prototype = AssetManager.search("prototype", entity["prototype"]);
			if prototype != None:
				for box in prototype["boxes"]:
					colour = (255, 0, 0) if box["type"] == "blocker" else (0, 255, 0);
					x0, y0, x1, y1 = box["aabb"];
					x0, y0, x1, y1 = x0+x, y0+y, x1+x, y1+y;
					self.canvas.draw_aabb((x0, y0, x1, y1), colour);

		if (
			"entity" in self.selection_context and 
			self.selection_context["entity"] == entity
		):
			aabb = self.get_entity_aabb(entity);
			self.canvas.draw_aabb(aabb, (255, 255, 255));
	
	def canvas_draw_tilemap(self):
		tm = self.scene["tilemap"];
		palette = SpriteBank.get(tm["palette"]);

		match tm["type"]:
			case "sparse":
				for tile in tm["sparse"]:
					
					frame_idx = clamp(tile["frame_idx"], 0, palette.frame_count-1);
					self.canvas.draw_image(
						tile["position"][0], tile["position"][1],
						palette.frame_images[frame_idx]
					);

				if self.edit_mode == EditMode.TILEMAP:
					cursor = self.canvas_io.get_cursor();
					grid_cursor = self.canvas_grid.snap_point(cursor);
					x0, y0 = grid_cursor;
					x1, y1 = x0+16, y0+16;
					self.canvas.draw_aabb(
						(x0, y0, x1, y1),
						(255, 255, 255),
					);
			case "dense":
				x0, y0 = tm["dense"]["position"];
				w = tm["dense"]["columns"];
				for row in range(tm["dense"]["rows"]):
					y = y0 + row * 16;
					for col in range(tm["dense"]["columns"]):
						x = x0 + col * 16;
						frame_idx = tm["dense"]["frame_indices"][row * w + col]-1;
						if frame_idx >= 0:
							frame_idx = clamp(frame_idx, 0, palette.frame_count-1);
							self.canvas.draw_image(
								x, y,
								palette.frame_images[frame_idx]
							);
	
	def canvas_draw_walls(self):
		if self.scene["has_bounds"]:
			self.canvas.draw_aabb(self.scene["bounds"], (128, 0, 0), False);
		for wall in self.scene["walls"]:
			colour = (255, 255, 0) if self.wall_editor.is_selected(wall) else (255, 0, 0);
			if wall["type"] == "aabb":
				self.canvas.draw_aabb(wall["aabb"], colour, False);
			elif wall["type"] == "segment":
				(x0, y0), (x1, y1) = wall["segment"];
				self.canvas.draw_line(x0, y0, x1, y1, colour);		
				self.canvas.draw_circle(x0, y0, 2, colour);
				self.canvas.draw_circle(x1, y1, 2, colour);
	
	def canvas_draw_texts(self):
		for text in self.scene["texts"]:
			self.canvas.draw_text(text["position"], text["text"], 8*text["scale"], text["colour"]);
			self.canvas.draw_aabb(self.text_editor.get_text_aabb(text), (255, 255, 255));
		
	def gui_draw_canvas(self):
		imgui.set_next_item_width(128);
		self.edit_mode = imgui_enum_selector(id(self.edit_mode), EditMode, self.edit_mode);

		self.show_entities = True;
		self.show_tiles = True;
		self.show_texts = True;

		self.show_grid = False;
		self.show_walls = True;
		self.show_boxes = False;

		self.snap_to_grid = True;

		imgui.same_line();
		_, self.canvas_config.show_entities = imgui.checkbox("Entites", self.canvas_config.show_entities);
		imgui.same_line();
		_, self.canvas_config.show_tiles = imgui.checkbox("Tiles", self.canvas_config.show_tiles);
		imgui.same_line();
		_, self.canvas_config.show_texts = imgui.checkbox("Texts", self.canvas_config.show_texts);

		imgui.same_line();
		_, self.canvas_config.show_grid = imgui.checkbox("Grid", self.canvas_config.show_grid);
		imgui.same_line();
		_, self.canvas_config.show_walls = imgui.checkbox("Walls", self.canvas_config.show_walls);
		imgui.same_line();
		_, self.canvas_config.show_boxes = imgui.checkbox("Boxes", self.canvas_config.show_boxes);

		imgui.same_line();
		imgui.set_next_item_width(64);
		_, self.canvas_grid.size = imgui.slider_int("Grid size", round(self.canvas_grid.size / 2) * 2, 2, 16);
		imgui.same_line();
		_, self.canvas_config.snap_to_grid = imgui.checkbox("Snap", self.canvas_config.snap_to_grid);

		r, g, b = self.scene["background"];
		self.canvas.clear((r, g, b));

		if self.canvas_config.show_tiles:
			self.canvas_draw_tilemap();

		if self.canvas_config.show_grid and self.canvas_grid.size >= 4:
			self.canvas_grid.draw_lines((64, 64, 64));
		self.canvas.draw_guides((255, 255, 255));
		
		if self.canvas_config.show_entities:
			def sort_y(entity):
				base_y = self.get_entity_aabb(entity)[3];
				prototype = AssetManager.search("prototype", entity["prototype"]);
				y_offset = prototype["y_sort_offset"] if prototype != None else 0;
				return base_y+y_offset;
			y_sorted = self.scene["entities"];
			y_sorted = sorted(y_sorted, key=lambda x: x["layer"]);
			y_sorted = sorted(y_sorted, key=sort_y);
			for entity in y_sorted:
				self.canvas_draw_entity(entity);
		
		if self.canvas_config.show_texts:
			self.canvas_draw_texts();
		
		if self.canvas_config.show_walls:
			self.canvas_draw_walls();
		
		if InputManager.is_held(glfw.KEY_LEFT_SHIFT) and self.canvas_io.cursor_in_bounds():
			x, y = self.canvas_io.get_cursor();
			self.canvas.draw_text((x, y), f"({int(x)}, {int(y)})", 16, (255, 255, 255));

		self.canvas.render();
	
	def draw(self):
		self.gui_draw_scene_selector();
		if not self._is_scene_loaded():
			return;

		self.manip_bookkeeping_tick();
		self.copypaste_tick();
		self.undo_tick();
		self.handle_events();

		match self.edit_mode:
			case EditMode.ENTITIES:
				imgui.begin_child(
					"Entity Window",
					imgui.ImVec2((imgui.get_content_region_avail().x - self.canvas.width) * 0.9, imgui.get_content_region_avail().y),
					0, 0
				);
				self.gui_draw_entities();
				imgui.end_child();
			case EditMode.TILEMAP:
				imgui.begin_child(
					"Tilemap Window",
					imgui.ImVec2(imgui.get_content_region_avail().x - self.canvas.width, imgui.get_content_region_avail().y),
					0, 0
				);
				self.tilemap_editor.gui_draw_palette();
				imgui.end_child();
			case EditMode.WALLS:
				imgui.begin_child(
					"Walls Window",
					imgui.ImVec2(imgui.get_content_region_avail().x - self.canvas.width, imgui.get_content_region_avail().y),
					0, 0
				);
				self.wall_editor.gui_draw_walls();
				imgui.end_child();
			case EditMode.TEXTS:
				imgui.begin_child(
					"Texts Window",
					imgui.ImVec2(imgui.get_content_region_avail().x - self.canvas.width, imgui.get_content_region_avail().y),
					0, 0
				);
				self.text_editor.gui_draw_texts();
				imgui.end_child();
			case EditMode.PROPERTIES:
				imgui.begin_child(
					"Properties Window",
					imgui.ImVec2(imgui.get_content_region_avail().x - self.canvas.width, imgui.get_content_region_avail().y),
					0, 0
				);
				self.gui_draw_properties_editor();
				imgui.end_child();

		imgui.same_line();
		imgui.begin_child(
			"Scene Window",
			imgui.ImVec2(imgui.get_content_region_avail().x, imgui.get_content_region_avail().y),
			0, 0
		);

		self.canvas_io.tick();
		self.gui_draw_canvas();
		match self.edit_mode:
			case EditMode.ENTITIES:
				self.canvas_manip.tick();
			case EditMode.TILEMAP:
				self.tilemap_editor.tick();
			case EditMode.WALLS:
				self.wall_editor.tick();
			case EditMode.TEXTS:
				self.text_editor.tick();
		
		imgui.end_child();
		