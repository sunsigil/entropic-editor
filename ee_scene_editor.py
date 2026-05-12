from imgui_bundle import imgui;
import glfw;

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
	TILEMAP = 1

class CanvasConfig:
	def __init__(self):
		self.show_grid = False;
		self.show_bounds = True;

class CreateEntityEvent:
	def __init__(self, source=None):
		self.source = source;

class DeleteEntityEvent:
	def __init__(self, entity):
		self.entity = entity;

class CreateTileEvent:
	def __init__(self, position, frame_idx):
		self.position = position;
		self.frame_idx = frame_idx;

class DeleteTileEvent:
	def __init__(self, tile):
		self.tile = tile

class TilemapEditor:
	def __init__(self, parent):
		self.parent = parent;
		self.tilemap = self.parent.scene["tilemap"];
		self.selected_frame = 0;

		self.dedup();
		self.clamp();

	def gui_draw_palette(self):
		sprite = SpriteBank.get(self.parent.scene["tilemap"]["palette"]);
		if sprite == None:
			return;

		wdw_w = imgui.get_content_region_avail().x;
		cols = int(wdw_w // 72);
		rows = int(math.ceil(sprite.frame_count / cols));

		i = 0;
		for r in range(rows):
			for c in range(cols):
				if i < sprite.frame_count:
					tint = (0.5, 0.5, 0.5, 1) if i == self.selected_frame else (1, 1, 1, 1);
					if imgui.image_button(f"##{id(i)}", sprite.frame_textures[i], (64, 64), tint_col=tint):
						self.selected_frame = i;
					imgui.same_line();
				i += 1;
			imgui.new_line();
	
	def spatial_search(self, position):
		x, y = self.parent.canvas_grid.snap_point(position);
		tile = next((t for t in self.tilemap["tiles"] if t["position"][0] == x and t["position"][1] == y), None);
		return tile;

	def is_occupied(self, position):
		return self.spatial_search(position) != None;

	def dedup(self):
		for tile in self.tilemap["tiles"]:
			if not self.spatial_search(tile["position"]) is tile:
				self.parent.event_queue.append(DeleteTileEvent(tile));
	
	def clamp(self):
		sprite = SpriteBank.get(self.tilemap["palette"]);
		frames = sprite.frame_count if sprite != None else 1;
		if self.selected_frame != None:
			self.selected_frame = clamp(self.selected_frame, 0, frames-1);
		for tile in self.tilemap["tiles"]:
			tile["frame_idx"] = clamp(tile["frame_idx"], 0, frames-1);

	def tick(self):
		if self.parent.canvas_io.cursor_in_bounds():
			if InputManager.is_held(glfw.MOUSE_BUTTON_LEFT):
				cursor = self.parent.canvas_io.get_cursor();
				tile_cursor = self.parent.canvas_grid.snap_point(cursor);
				if InputManager.is_held(glfw.KEY_LEFT_SHIFT):
					for idx, tile in enumerate(self.tilemap["tiles"]):
						tx, ty = self.parent.canvas_grid.snap_point(tile["position"]);
						cx, cy = tile_cursor;
						if int(tx) == int(cx) and int(ty) == int(cy):
							self.parent.event_queue.append(DeleteTileEvent(self.tilemap["tiles"][idx]));
				elif self.selected_frame != None:
					existing = self.spatial_search(tile_cursor);
					if existing == None:
						self.parent.event_queue.append(CreateTileEvent(tile_cursor, self.selected_frame));
					else:
						existing["frame_idx"] = self.selected_frame;

class SceneEditor:
	def __init__(self):
		self.canvas_size = (720, 720);
		self.tile_size = 16;
		self.canvas = Canvas(self.canvas_size[0], self.canvas_size[1], origin=(self.canvas_size[0]//2, self.canvas_size[1]//2));
		self.canvas_io = CanvasIO(self.canvas);
		self.canvas_grid = CanvasGrid(
			self.canvas,
			self.tile_size
		);

		self.canvas_manip = CanvasManipulator(self.canvas_io);
		self.manip_map = {};
		self.canvas_manip.click_callback = self.manip_click_handler;
		self.canvas_manip.drag_callback = self.manip_drag_handler;

		self.canvas_config = CanvasConfig();

		self.load_scene(AssetManager.get_first("scene"));
	
	def load_scene(self, scene):		
		self.scene = scene;
		if scene != None:
			self.event_queue = [];
			self.selection_context = {};
			self.clipboard = [];
			self.edit_mode = EditMode.ENTITIES;
			self.tilemap_editor = TilemapEditor(self);

	def is_scene_loaded(self):
		return self.scene in AssetManager.get_assets("scene");

	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CreateEntityEvent):
				entity = {
						"name": "",
						"prototype": "",
						"position": [0, 0]
				};
				if event.source != None:
					entity["name"] = f"{event.source["name"]} (Copy)";
					entity["prototype"] = event.source["prototype"];
					entity["position"] = list(event.source["position"]);
				self.scene["entities"].append(entity);
			if isinstance(event, DeleteEntityEvent):
				self.scene["entities"].remove(event.entity);

			if isinstance(event, CreateTileEvent):
				self.scene["tilemap"]["tiles"].append(
					{
						"position": list(event.position),
						"frame_idx": event.frame_idx
					}
				);
			if isinstance(event, DeleteTileEvent):
				self.scene["tilemap"]["tiles"].remove(event.tile)
	
	def get_entity_sprite(self, entity):
		prototype = AssetManager.search("prototype", entity["prototype"]);
		return SpriteBank.get(prototype["sprite"] if prototype != None else "null");

	def get_entity_aabb(self, entity):
		sprite = self.get_entity_sprite(entity);
		x0, y0 = entity["position"];
		x1, y1 = x0 + sprite.frame_width, y0 + sprite.frame_height;
		return (x0, y0, x1, y1);

	def select_entity(self, entity):
		if entity == None:
			self.selection_context = {};
		else:
			self.selection_context = { "entity": entity };

	def get_selected_entity(self):
		return None if not "entity" in self.selection_context else self.selection_context["entity"];
	
	def manip_click_handler(self, click):
		if click.eeid == None:
			self.selection_context = {};
		else:
			self.selection_context["entity"] = self.manip_map[click.eeid];
	
	def manip_drag_handler(self, drag):
		entity = self.manip_map[drag.eeid];
		match drag.signal:
			case CanvasManipDrag.Signal.START:
				entity = self.manip_map[drag.eeid];
				delta = entity["position"][0] - drag.point[0], entity["position"][1] - drag.point[1];
				self.select_entity(entity);
				self.selection_context["delta"] = delta;
			case CanvasManipDrag.Signal.TICK:
				entity = self.selection_context["entity"];
				point = drag.point;
				delta = self.selection_context["delta"];
				entity["position"] = point[0] + delta[0], point[1] + delta[1];
	
	def refresh_manip_state(self):
		for entity in self.scene["entities"]:
			if entity not in self.manip_map.values():
				aabb = self.get_entity_aabb(entity);
				eeid = self.canvas_manip.register(aabb, fill=True);
				self.manip_map[eeid] = entity
		
		for k,v in self.manip_map.items():
			aabb = self.get_entity_aabb(v);
			shape = self.canvas_manip.get(k);
			shape.update(aabb);
	
	def copypaste_tick(self):
		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_C):
			if "entity" in self.selection_context:
				self.clipboard = [self.selection_context["entity"]];
		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_V):
			for entity in self.clipboard:
				self.event_queue.append(CreateEntityEvent(entity));
	
	def gui_draw_scene_selector(self):
		scene_last = self.scene;
		self.scene = imgui_asset_selector(id(self.scene), "scene", self.scene);
		if self.scene != scene_last:
			self.load_scene(self.scene);
	
	def gui_draw_entity(self, entity):
		name = entity["name"] if len(entity["name"]) > 0 else str(id(entity));

		selected = entity == self.get_selected_entity();
		imgui.set_next_item_open(selected);
		node_open = imgui.tree_node(f"{name}####{id(entity)}");

		if imgui.begin_popup_context_item(str(id(entity))):
			if imgui.menu_item_simple("Delete"):
				self.event_queue.append(DeleteEntityEvent(entity));
				imgui.close_current_popup();
			imgui.end_popup();
		
		if node_open:
			if not selected:
				self.select_entity(entity);
			
			_, entity["name"] = imgui.input_text("Name", entity["name"]);
			
			proto_names = [x["name"] for x in AssetManager.get_assets("prototype")] + [None];
			entity["prototype"] = imgui_selector(id(entity["prototype"]), proto_names, entity["prototype"]);

			imgui.tree_pop();
	
	def gui_draw_entities(self):
		entities_open = imgui.tree_node("Entities");
		if imgui.begin_popup_context_item("Create"):
			if imgui.menu_item_simple("New entity"):
				self.event_queue.append(CreateEntityEvent());
				imgui.close_current_popup();
			imgui.end_popup();
		
		if entities_open:
			for entity in self.scene["entities"]:
				self.gui_draw_entity(entity);
			imgui.tree_pop();
	
	def gui_draw_properties_editor(self):
		_, self.scene["bounds"] = imgui.input_int4("Bounds", self.scene["bounds"]);

		r, g, b = self.scene["background"];
		_, (r, g, b) = imgui.color_edit3("Background", (r/255, g/255, b/255));
		self.scene["background"] = [int(r*255), int(g*255), int(b*255)];

		palette = self.scene["tilemap"]["palette"];
		self.scene["tilemap"]["palette"] = imgui_asset_name_selector(id(self.scene["tilemap"]["palette"]), "sprite", self.scene["tilemap"]["palette"]);
		if self.scene["tilemap"]["palette"] != palette:
			self.tilemap_editor.clamp();
	
	def canvas_draw_entity(self, entity):
		x, y = entity["position"];
		sprite = self.get_entity_sprite(entity);
		self.canvas.draw_image(x, y, sprite.frame_images[0]);

		if (
			"entity" in self.selection_context and 
			self.selection_context["entity"] == entity
		):
			aabb = self.get_entity_aabb(entity);
			self.canvas.draw_aabb(aabb, (255, 255, 255));
	
	def canvas_draw_tilemap(self):
		for tile in self.scene["tilemap"]["tiles"]:
			sprite = SpriteBank.get(self.scene["tilemap"]["palette"]);
			self.canvas.draw_image(
				tile["position"][0], tile["position"][1],
				sprite.frame_images[tile["frame_idx"]]
			);
		
	def gui_draw_canvas(self):
		imgui.set_next_item_width(128);
		self.edit_mode = imgui_enum_selector(id(self.edit_mode), EditMode, self.edit_mode);
		imgui.same_line();
		_, self.canvas_config.show_grid = imgui.checkbox("Show grid", self.canvas_config.show_grid);
		imgui.same_line();
		_, self.canvas_config.show_bounds = imgui.checkbox("Show bounds", self.canvas_config.show_bounds);

		r, g, b = self.scene["background"];
		self.canvas.clear((r, g, b));

		self.canvas_draw_tilemap();

		if self.canvas_config.show_grid:
			self.canvas_grid.draw_lines((64, 64, 64));
			self.canvas.draw_guides((255, 255, 255));
		
		for entity in self.scene["entities"]:
			self.canvas_draw_entity(entity);

		if self.canvas_config.show_bounds:
			x0, y0, x1, y1 = self.scene["bounds"];
			self.canvas.draw_aabb((x0, y0, x1, y1), (255, 0, 0));

		self.canvas.render();
	
	def draw(self):
		self.gui_draw_scene_selector();
		if not self.is_scene_loaded():
			return;

		self.refresh_manip_state();
		self.copypaste_tick();
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

		imgui.same_line();
		imgui.begin_child(
			"Scene Window",
			imgui.ImVec2(imgui.get_content_region_avail().x, imgui.get_content_region_avail().y),
			0, 0
		);

		if imgui.begin_tab_bar("Scene Tabs"):

			if imgui.begin_tab_item("Scene")[0]:
				self.canvas_io.tick();
				self.gui_draw_canvas();
				if self.edit_mode == EditMode.ENTITIES:
					self.canvas_manip.tick();
				else:
					self.tilemap_editor.tick();
				imgui.end_tab_item();
			
			if imgui.begin_tab_item("Properties")[0]:
				self.gui_draw_properties_editor();
				imgui.end_tab_item();
			imgui.end_tab_bar();
		
		imgui.end_child();
		