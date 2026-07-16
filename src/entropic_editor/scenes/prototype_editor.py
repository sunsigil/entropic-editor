from imgui_bundle import imgui;
import glfw;
from enum import Enum;

from cowtools import *;
from canvas import *
from assets import *;
from sprites import SpriteBank;
from input import InputManager;
from editor_gui import *;
from geometry import *;
import scenes.walls;
import scripts;

class PrototypeSpawner:
	def __init__(self):
		self.size = (512, 256);
		self.sprite = "";
		self.static = True;
		self.finished = False;

	def draw(self):
		imgui.set_next_window_size(self.size);
		_, open = imgui.begin("Create prototype", not self.finished);

		self.sprite = input_asset("Sprite", self.sprite, "sprite");
		self.static = input_bool("Static", self.static);

		if AssetManager.search("sprite", self.sprite) != None:
			if imgui.button("Create"):
				prototype = AssetManager.get_document("prototype").spawn_entry();
				prototype["name"] = self.sprite;
				prototype["sprite"] = self.sprite;
				sprite = SpriteBank.search(self.sprite);
				prototype["sprite_offset"] = [-sprite.frame_width//2, -sprite.frame_height];

				if self.static:
					prototype["walls"].append({
						"type": "aabb",
						"aabb": [-sprite.frame_width//2, -8, sprite.frame_width//2, 0]
					});
				else:
					prototype["has_blocker"] = True;
					prototype["blocker"] = [-sprite.frame_width//2, -8, sprite.frame_width//2, 0];
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
			self.canvas.origin = (128, 128);
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
		self.selection_context = SelectionContext();

		self.prototype_spawner = None;
		self.draw_grid = True;
		self.draw_outlines = False;
		
		self.tabs = ["sprite", "boxes", "anchors", "walls"];
		self.tab = self.tabs[0];

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
		self.prototype["has_blocker"] = input_bool("Has blocker", self.prototype["has_blocker"]);
		if self.prototype["has_blocker"]:
			self.prototype["blocker"] = input_aabb("Blocker", self.prototype["blocker"]);
		self.prototype["has_trigger"] = input_bool("Has trigger", self.prototype["has_trigger"]);
		if self.prototype["has_trigger"]:
			self.prototype["trigger"] = input_aabb("Trigger", self.prototype["trigger"]);
			self.prototype["trigger_orientation"] = input_enum("Trigger orientation", self.prototype["trigger_orientation"], ["none", "east", "north", "west", "south"]);
			if self.prototype["has_blocker"] and imgui.button("Conform to blocker"):
				self.prototype["trigger"] = list(self.prototype["blocker"]);
	
	def gui_draw_scripts(self):	
		scripts_open = imgui.tree_node("Scripts");
		if imgui.begin_popup_context_item():
			if imgui.menu_item_simple("New script"):
				self.prototype["scripts"].append("");
			imgui.end_popup();
		
		if scripts_open:
			trash = [];
			for i in range(len(self.prototype["scripts"])):
				script = self.prototype["scripts"][i];

				self.prototype["scripts"][i] = input_asset(f"##script {i}", self.prototype["scripts"][i], "script");
				if ContextMenu.begin(f"##script {i}"):
					if imgui.menu_item_simple("Delete"):
						trash.append(i);
					imgui.end_popup();
			
			while len(trash) > 0:
				i = trash.pop();
				del self.prototype["scripts"][i];
			imgui.tree_pop();

		if imgui.tree_node("Script Data"):
			scripts.rectify_prototype(self.prototype);

			for sd_inst in self.prototype["script_data"]:
				sd = scripts.ScriptData(sd_inst["signature"]["key"], sd_inst["signature"]["type"]);
				label = f"{sd.key} ({sd.type})";
				sd_inst = next(x for x in self.prototype["script_data"] if x["signature"]["key"] == sd.key);
				sd_inst["value"] = typed_input(label, sd.type, sd_inst["value"]);
					
			imgui.tree_pop();
	
	def canvas_draw_boxes(self):
		if self.prototype["has_blocker"]:
			self.canvas.draw_aabb(self.prototype["blocker"], (255, 128, 0));
		if self.prototype["has_trigger"]:
			self.canvas.draw_aabb(self.prototype["trigger"], (0, 255, 0));
			x0, y0, x1, y1 = self.prototype["trigger"];
			mx, my = (x0+x1)/2, (y0+y1)/2;
			match self.prototype["trigger_orientation"]:
				case "north":
					self.canvas.draw_line(mx, y0, mx, y0-16, (0, 255, 0));
				case "east":
					self.canvas.draw_line(x1, my, x1+16, my, (0, 255, 0));
				case "south":
					self.canvas.draw_line(mx, y1, mx, y1+16, (0, 255, 0));
				case "west":
					self.canvas.draw_line(x0, my, x0-16, my, (0, 255, 0));			
	
	def gui_draw_canvas(self):
		self.canvas.clear((128, 128, 128));
		if self.draw_grid:
			self.canvas_grid.draw_lines((64, 64, 64));
			self.canvas.draw_guides((192, 192, 192));

		if self.prototype != None:
			sprite = SpriteBank.search(self.prototype["sprite"], safe=False);
			if sprite != None:
				x, y = self.prototype["sprite_offset"];

				self.canvas.draw_image(x, y, sprite.frame_images[0]);
				if self.draw_outlines:
					self.canvas.draw_aabb((x, y, x+sprite.frame_width, y+sprite.frame_height), (255, 255, 255));

				y = self.prototype["sprite_offset"][1] + sprite.frame_height + self.prototype["y_sort_offset"];
				w = self.canvas.width;
				self.canvas.draw_line(-w, y, w, y, (255, 255, 0));

			if self.prototype["override_prompt_position"]:
				x, y = self.prototype["prompt_position"];
				self.canvas.draw_line(x-4, y, x+4, y, (255, 255, 0));
				self.canvas.draw_line(x, y-4, x, y+4, (255, 255, 0));
			
			for wall in self.prototype["walls"]:
				scenes.walls.canvas_draw(self.canvas, wall, (255, 0, 0));

			self.canvas_draw_boxes();
	
		self.canvas.render();
		ContextMenu.ping("prototype-canvas");

		self.canvas_io.tick();
		self.canvas_manip.tick();
	
	def synchronize_manip(self):
		paths = [];
		shapes = [];

		match self.tab:
			case "sprite":
				sprite = SpriteBank.search(self.prototype["sprite"]);
				if sprite != None:
					paths.append("sprite");
					x0, y0 = self.prototype["sprite_offset"];
					x1, y1 = x0+sprite.frame_width, y0+sprite.frame_height;
					shapes.append(CanvasManipRect([x0, y0, x1, y1]));
			case "boxes":
				if self.prototype["has_blocker"]:
					paths.append("blocker");
					shapes.append(CanvasManipRect(self.prototype["blocker"]));
				if self.prototype["has_trigger"]:
					paths.append("trigger");
					shapes.append(CanvasManipRect(self.prototype["trigger"]));
			case "anchors":
				if self.prototype["override_prompt_position"]:
					paths.append("prompt_position");
					shapes.append(CanvasManipPoint(self.prototype["prompt_position"]));
			case "walls":
				for idx,wall in enumerate(self.prototype["walls"]):
					paths.append(f"walls/{idx}");
					if wall["type"] == "aabb":
						shapes.append(CanvasManipRect(wall["aabb"]));
					if wall["type"] == "segment":
						shapes.append(CanvasManipSegment(wall["segment"]));
		
		self.manip_registry.update(paths, shapes);
		self.canvas_manip.synchronize(self.manip_registry);
	
	def view_drag_handler(self, event):
		match event.signal:
			case CanvasManipDrag.Signal.TICK:
				x0, y0 = event.start;
				x, y = event.point;
				dx, dy = x-x0, y-y0;
				
				ox, oy = self.canvas.origin;
				self.canvas.origin = ox+dx, oy+dy;
	
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
				self.canvas_grid.size = input_int("Grid size", self.canvas_grid.size, style=EEGUIIntStyle.SLIDER, low_bound=2, high_bound=16);
				_, self.draw_outlines = imgui.menu_item("Show outlines", "", self.draw_outlines);
				imgui.end_menu();
			imgui.end_menu_bar();
		
		if self.prototype_spawner != None:
			self.prototype_spawner.draw();
			if self.prototype_spawner.is_finished():
				self.prototype_spawner = None;

		begin_column("left-panel", imgui.get_content_region_avail().x * 0.15);
		self.gui_draw_selector();
		end_column();

		begin_column("main-panel");

		self.prototype["name"] = input_string("Name", self.prototype["name"]);

		if imgui.begin_tab_bar("edit-mode"):
			for value in self.tabs:
				tab_visible, tab_open = imgui.begin_tab_item(value);
				if tab_visible:
					self.tab = value;
					imgui.end_tab_item();
			imgui.end_tab_bar();

		self.gui_draw_canvas();
		if ContextMenu.begin("prototype-canvas"):
			if self.tab == "walls":
				if imgui.begin_menu("New wall"):
					if imgui.menu_item_simple("AABB"):
						self.prototype["walls"].append(scenes.walls.canvas_place(self.canvas_io.get_cursor(), "aabb", self.canvas_grid));
					if imgui.menu_item_simple("Segment"):
						self.prototype["walls"].append(scenes.walls.canvas_place(self.canvas_io.get_cursor(), "segment", self.canvas_grid));
					imgui.end_menu();
			imgui.end_popup();

		self.prototype["sprite"] = input_asset("Sprite", self.prototype["sprite"], "sprite");
		self.prototype["sprite_offset"] = input_vec2("Sprite offset", self.prototype["sprite_offset"]);
		self.prototype["y_sort_offset"] = input_int("Y-sort offset", self.prototype["y_sort_offset"]);
		self.prototype["override_prompt_position"] = input_bool("Override prompt position", self.prototype["override_prompt_position"]);
		if self.prototype["override_prompt_position"]:
			imgui.same_line();
			self.prototype["prompt_position"] = input_vec2("Prompt positon", self.prototype["prompt_position"]);
		
		self.prototype["mobile"] = input_bool("Mobile", self.prototype["mobile"]);
		imgui.same_line();
		self.prototype["animated"] = input_bool("Animated", self.prototype["animated"]);
		
		self.gui_draw_boxes();
		self.gui_draw_scripts();
		
		end_column();

		self.synchronize_manip();

		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);
			
			if isinstance(event, CanvasManipClick):
				if event.eeid == None:
					self.selection_context.clear();
				else:
					self.selection_context.select(self.manip_registry.search(event.eeid));
			
			if isinstance(event, CanvasManipDrag):
				if event.eeid == None:
					self.view_drag_handler(event);
					return;
			
				shape = self.canvas_manip.search(event.eeid);
				path = self.manip_registry.search(event.eeid);
			
				match event.signal:
					case CanvasManipDrag.Signal.TICK:
						if path == "sprite":
							x, y = event.point;
							dx, dy = event.delta;
							x, y = self.canvas_grid.snap_point((x+dx, y+dy));
							self.prototype["sprite_offset"] = x, y;
						
						elif path == "blocker" or path == "trigger":
							box = get_by_path(self.prototype, path);
							edge = aabb_closest_edge(event.geometry, event.start);
							if event.inside:
								point = np.array(event.point) + np.array(event.delta);
								point = self.canvas_grid.snap_point(point);
								set_by_path(self.prototype, path, relocate_aabb(box, point));
							else:
								point = self.canvas_grid.snap_point(event.point);
								set_by_path(self.prototype, path, shape_aabb(box, edge, point));
						
						elif path == "prompt_position":
							point = get_by_path(self.prototype, self.manip_registry.search(event.eeid));
							point[0] = event.point[0];
							point[1] = event.point[1];
						
						elif "walls" in path:
							wall = get_by_path(self.prototype, path);
							scenes.walls.canvas_drag(wall, event, self.canvas_grid);
					
					case CanvasManipDrag.Signal.END:
						self.selection_context.clear();