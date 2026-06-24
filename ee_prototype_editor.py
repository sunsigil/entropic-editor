from imgui_bundle import imgui;
import glfw;
from enum import Enum;

from ee_cowtools import *;
from ee_canvas import *
from ee_assets import *;
from ee_sprites import SpriteBank;
from ee_input import InputManager;
from ee_imgui import *;
from ee_geometry import *;

class PrototypeSpawner:
	def __init__(self):
		self.size = (512, 256);
		self.prototype = {
			"sprite": "",
			"boxes": []
		};
		self.finished = False;
	
	def autofill(self):
		if len(self.prototype["sprite"]) > 0:
			self.prototype["name"] = self.prototype["sprite"];
		sprite = SpriteBank.search(self.prototype["sprite"]);
		height = min(sprite.frame_width, sprite.frame_height);
		self.prototype["boxes"].append({
			"aabb": [0, sprite.frame_height-height, sprite.frame_width, sprite.frame_height],
			"orientation": "none",
			"type": "blocker"
		});

	def draw(self):
		imgui.set_next_window_size(self.size);
		_, open = imgui.begin("Create prototype", not self.finished);

		self.prototype["sprite"] = eegui_input_asset("sprite", self.prototype["sprite"], "sprite");
	
		if AssetManager.search("sprite", self.prototype["sprite"]) != None:
			if imgui.button("Create"):
				self.autofill();
				AssetManager.get_document("prototype").spawn_entry(source=self.prototype);
				self.finished = True;
			imgui.same_line();
		if imgui.button("Cancel"):
			self.finished = True;
		
		self.size = imgui.get_window_size();
		imgui.end();
		
		if not open:
			self.finished = True;

	def is_finished(self):
		return self.finished;

class PrototypeEditor:
	def _load_prototype(self, prototype):
		self.prototype = prototype;
		if prototype != None:
			sprite = SpriteBank.search(self.prototype["sprite"]);
			self.canvas.origin = (128-sprite.frame_width//2, 128-sprite.frame_height//2);
			self.canvas_manip.clear();
			self.manip_registry = CanvasManipRegistry();
	
	def __init__(self):
		self.canvas_size = (256, 256);

		self.canvas = Canvas(self.canvas_size[0], self.canvas_size[1], scale=2, origin=(128, 128));
		self.canvas_io = CanvasIO(self.canvas);
		self.canvas_grid = CanvasGrid(
			self.canvas,
			4
		);

		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(self.canvas_io, self.event_queue);
		self.manip_registry = CanvasManipRegistry();
		self.selection_context = {};

		self.prototype_spawner = None;
		self.draw_grid = True;

		self._load_prototype(AssetManager.get_first("prototype"));
	
	def gui_draw_selector(self):
		protoypes = sorted(AssetManager.get_all("prototype"), key=lambda x: x["name"]);

		for prototype in protoypes:
			selected = imgui.menu_item_simple(prototype["name"]+f"##{id(prototype)}");

			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("Delete"):
					AssetManager.get_document("prototype").delete_entry(prototype);
					imgui.close_current_popup();
				imgui.end_popup();
			
			if selected:
				self._load_prototype(prototype);
	
	def gui_draw_boxes(self):
		boxes_open = imgui.tree_node("Boxes");
		if imgui.begin_popup_context_item():
			if imgui.menu_item_simple("New blocker"):
				self.prototype["boxes"].append({
					"aabb": [0, 0, 16, 16],
					"orientation": "none",
					"type": "blocker"
				});
			if imgui.menu_item_simple("New trigger"):
				self.prototype["boxes"].append({
					"aabb": [0, 0, 16, 16],
					"orientation": "south",
					"type": "trigger"
				});
			imgui.end_popup();
		
		if boxes_open:
			trash = [];

			for i, box in enumerate(self.prototype["boxes"]):
				node_open = imgui.tree_node(f"{box["type"].title()} {i}");
				if imgui.begin_popup_context_item():
					if imgui.menu_item_simple("Delete"):
						trash.append(box);
						imgui.close_current_popup();
					imgui.end_popup();

				if node_open:
					box["type"] = eegui_combo("Type", box["type"], ["trigger", "blocker"]);
					box["orientation"] = eegui_combo("Orientation", box["orientation"], ["none", "north", "east", "south", "west"]);
					box["aabb"] = eegui_input_aabb("AABB", box["aabb"]);
					imgui.tree_pop();

			process_trash(self.prototype["boxes"], trash);

			imgui.tree_pop();
	
	def gui_draw_scripts(self):
		scripts_open = imgui.tree_node("Scripts");
		if imgui.begin_popup_context_item():
			if imgui.menu_item_simple("New script"):
				self.prototype["scripts"].append("");
			imgui.end_popup();
		
		if scripts_open:
			trash = [];
			for i in range(len(self.prototype["scripts"])):
				self.prototype["scripts"][i] = eegui_input_asset(f"Script {i}", self.prototype["scripts"][i], "script");
				if EEGUIContextMenu.begin(f"Script {i}"):
					if imgui.menu_item_simple("Delete"):
						trash.append(i);
					imgui.end_popup();
			
			while len(trash) > 0:
				i = trash.pop();
				del self.prototype["scripts"][i];
			imgui.tree_pop();
	
	def canvas_draw_boxes(self):
		for box in self.prototype["boxes"]:
			colour = (255, 0, 0) if box["type"] == "blocker" else (0, 255, 0);

			x0, y0, x1, y1 = box["aabb"];
			mx, my = (x0+x1)/2, (y0+y1)/2;
			self.canvas.draw_aabb(box["aabb"], colour);

			match box["orientation"]:
				case "north":
					self.canvas.draw_line(mx, y0, mx, y0-16, colour);
				case "east":
					self.canvas.draw_line(x1, my, x1+16, my, colour);
				case "south":
					self.canvas.draw_line(mx, y1, mx, y1+16, colour);
				case "west":
					self.canvas.draw_line(x0, my, x0-16, my, colour);
	
	def gui_draw_canvas(self):
		self.canvas.clear((128, 128, 128));
		if self.draw_grid:
			self.canvas_grid.draw_lines((64, 64, 64));

		if self.prototype != None:
			sprite = SpriteBank.search(self.prototype["sprite"]);
			self.canvas.draw_image(0, 0, sprite.frame_images[0]);

			y = sprite.frame_height+self.prototype["y_sort_offset"];
			w = self.canvas.width;
			self.canvas.draw_line(-w, y, w, y, (255, 255, 0));

			if self.prototype["override_prompt_position"]:
				x, y = self.prototype["prompt_position"];
				self.canvas.draw_line(x-4, y, x+4, y, (255, 255, 0));
				self.canvas.draw_line(x, y-4, x, y+4, (255, 255, 0));

			self.canvas_draw_boxes();
	
		self.canvas.render();
		self.canvas_io.tick();
		self.canvas_manip.tick();
	
	def synchronize_manip(self):
		paths = [];
		for i in range(len(self.prototype["boxes"])):
			paths.append(f"boxes/{i}");
		paths.append("prompt_position");

		def make_shape(path):
			if "boxes" in path:
				return CanvasManipRect(get_by_path(self.prototype, path+"/aabb"));
			elif "position" in path:
				return CanvasManipPoint(get_by_path(self.prototype, path));
		shapes = [make_shape(x) for x in paths];
		
		self.manip_registry.update(paths, shapes);
		self.canvas_manip.synchronize(self.manip_registry);
	
	def draw(self):
		if imgui.begin_menu_bar():
			if imgui.begin_menu("Asset"):
				if imgui.menu_item_simple("New"):
					AssetManager.get_document("prototype").spawn_entry();
				if imgui.menu_item_simple("New from sprite"):
					self.prototype_spawner = PrototypeSpawner();
				imgui.end_menu();
			
			if imgui.begin_menu("View"):
				_, self.draw_grid = imgui.menu_item("Show grid", "", self.draw_grid);
				imgui.set_next_item_width(64);
				self.canvas_grid.size = eegui_input_int("Grid size", self.canvas_grid.size, style=EEGUIIntStyle.SLIDER, low_bound=2, high_bound=16);
				imgui.end_menu();
			imgui.end_menu_bar();
		
		if self.prototype_spawner != None:
			self.prototype_spawner.draw();
			if self.prototype_spawner.is_finished():
				self.prototype_spawner = None;

		eegui_begin_column("left-panel", imgui.get_content_region_avail().x * 0.15);
		self.gui_draw_selector();
		eegui_end_column();

		eegui_begin_column("main-panel");

		self.prototype["name"] = eegui_input_string("Name", self.prototype["name"]);

		self.gui_draw_canvas();

		self.prototype["sprite"] = eegui_input_asset("Sprite", self.prototype["sprite"], "sprite");
		self.prototype["y_sort_offset"] == eegui_input_int("Y Sort Offset", self.prototype["y_sort_offset"]);
		self.prototype["override_prompt_position"] = eegui_input_bool("Override prompt position", self.prototype["override_prompt_position"]);
		if self.prototype["override_prompt_position"]:
			imgui.same_line();
			self.prototype["prompt_position"] = eegui_input_vec2("Prompt positon", self.prototype["prompt_position"]);
		
		self.gui_draw_boxes();
		self.gui_draw_scripts();
		
		eegui_end_column();

		self.synchronize_manip();

		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);
			
			if isinstance(event, CanvasManipClick):
				if event.eeid == None:
					self.selection_context = {};
				else:
					self.selection_context = {
						"mode" : "click",
						"eeid": event.eeid
					};

				if InputManager.is_held(glfw.KEY_LEFT_SHIFT) and self.prototype["override_prompt_position"]:
					self.prototype["prompt_position"] = event.point;
			
			if isinstance(event, CanvasManipDrag):
				if event.eeid == None:
					return;
			
				match event.signal:
					case CanvasManipDrag.Signal.START:
						self.selection_context = {};
						self.selection_context["inside"] = event.distance <= -2;

						shape = self.canvas_manip.search(event.eeid);
						if isinstance(shape, CanvasManipRect):
							box = get_by_path(self.prototype, self.manip_registry.search(event.eeid));
							self.selection_context["edge"] = aabb_closest_edge(box["aabb"], event.point);

					case CanvasManipDrag.Signal.TICK:
						if self.selection_context != {}:
							shape = self.canvas_manip.search(event.eeid);
							if isinstance(shape, CanvasManipRect):
								box = get_by_path(self.prototype, self.manip_registry.search(event.eeid));
								edge = self.selection_context["edge"];
								point = self.canvas_grid.snap_point(event.point);
								if self.selection_context["inside"]:
									box["aabb"] = relocate_aabb(box["aabb"], point);
								else:
									box["aabb"] = shape_aabb(box["aabb"], edge, point);
							if isinstance(shape, CanvasManipPoint):
								point = get_by_path(self.prototype, self.manip_registry.search(event.eeid));
								point[0] = event.point[0];
								point[1] = event.point[1];
					
					case CanvasManipDrag.Signal.END:
						self.selection_context = {};