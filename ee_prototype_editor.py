from imgui_bundle import imgui;
import glfw;
from enum import Enum;

from ee_cowtools import *;
from ee_canvas import *
from ee_assets import *;
from ee_sprites import SpriteBank;
from ee_input import InputManager;
from ee_imgui import *;

class PrototypeSpawner:
	def __init__(self):
		self.size = (256, 128);
		self.prototype = {
			"sprite": "",
			"boxes": []
		};
		self.finished = False;
	
	def autofill(self):
		if len(self.prototype["sprite"]) > 0:
			self.prototype["name"] = self.prototype["sprite"];
		sprite = SpriteBank.get(self.prototype["sprite"]);
		height = min(sprite.frame_width, sprite.frame_height);
		self.prototype["boxes"].append({
			"aabb": [0, sprite.frame_height-height, sprite.frame_width, sprite.frame_height],
			"orientation": "none",
			"type": "blocker"
		});

	def draw(self):
		imgui.set_next_window_size(self.size);
		_, open = imgui.begin("Create prototype", not self.finished);

		self.prototype["sprite"] = imgui_asset_input("new_sprite", "sprite", self.prototype["sprite"]);
	
		if AssetManager.search("sprite", self.prototype["sprite"]) != None and imgui.button("Create"):
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
			sprite = SpriteBank.get(self.prototype["sprite"]);
			self.canvas.origin = (128-sprite.frame_width//2, 128-sprite.frame_height//2);

			self.canvas_manipulator.clear();
			self.manip_map = {};
			for box in self.prototype["boxes"]:
				eeid = self.canvas_manipulator.register_shape(box["aabb"]);
				self.manip_map[eeid] = id(box);
	
	def __init__(self):
		self.canvas_size = (256, 256);

		self.canvas = Canvas(self.canvas_size[0], self.canvas_size[1], scale=2, origin=(128, 128));
		self.canvas_io = CanvasIO(self.canvas);
		self.canvas_grid = CanvasGrid(
			self.canvas,
			4
		);

		self.event_queue = [];
		self.canvas_manipulator = CanvasManipulator(self.canvas_io, self.event_queue);
		self.manip_map = {};
		self.selection_context = {};

		self.prototype_spawner = None;

		self._load_prototype(AssetManager.get_first("prototype"));
	
	def search_manip_map(self, eeid):
		if self.prototype == None:
			return None;
		py_id = self.manip_map[eeid];
		for box in self.prototype["boxes"]:
			if id(box) == py_id:
				return box;
		return None;
	
	def gui_draw_selector(self):
		protoypes = sorted(AssetManager.get_assets("prototype"), key=lambda x: x["name"]);

		for prototype in protoypes:
			selected = imgui.menu_item_simple(prototype["name"]);

			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("New prototype"):
					self.prototype_spawner = PrototypeSpawner();
					imgui.close_current_popup();
				if imgui.menu_item_simple("Delete"):
					AssetManager.get_document("prototype").delete_entry(prototype);
					imgui.close_current_popup();
				imgui.end_popup();
			
			if selected:
				self._load_prototype(prototype);

		if self.prototype_spawner != None:
			self.prototype_spawner.draw();
			if self.prototype_spawner.is_finished():
				self.prototype_spawner = None;
	
	def gui_draw_boxes(self):
		trash = [];
		for i, box in enumerate(self.prototype["boxes"]):
			node_open = imgui.tree_node(f"{box["type"].title()} {i}##{id(box)}");

			if imgui.begin_popup_context_item(str(id(box))):
				if imgui.menu_item_simple("Delete"):
					trash.append(box);
					imgui.close_current_popup();
				imgui.end_popup();

			if node_open:
				box["type"] = imgui_selector(id(box["type"]), ["trigger", "blocker"], box["type"]);
				box["orientation"] = imgui_selector(id(box["orientation"]), ["none", "north", "east", "south", "west"], box["orientation"]);
				_, box["aabb"] = imgui.input_int4("AABB", box["aabb"]);
				imgui.tree_pop();
		for box in trash:
			self.prototype["boxes"].remove(box);
	
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
		imgui.set_next_item_width(64);
		_, self.canvas_grid.size = imgui.slider_int("Grid size", round(self.canvas_grid.size / 2) * 2, 2, 16);

		self.canvas.clear((128, 128, 128));
		self.canvas_grid.draw_lines((64, 64, 64));

		if self.prototype != None:
			sprite = SpriteBank.get(self.prototype["sprite"]);
			self.canvas.draw_image(0, 0, sprite.frame_images[0]);
			self.canvas_draw_boxes();
	
		self.canvas.render();
		self.canvas_io.tick();
		self.canvas_manipulator.tick();
	
	def draw(self):

		imgui_begin_column("prototype_window", imgui.get_content_region_avail().x * 0.15);
		self.gui_draw_selector();
		imgui_end_column();

		imgui_begin_column("scene_window");

		self.gui_draw_canvas();

		self.prototype["sprite"] = imgui_asset_input("sprite", "sprite", self.prototype["sprite"]);
		_, self.prototype["animated"] = imgui.checkbox("Animated", self.prototype["animated"]);

		scripts_open = imgui.tree_node("Scripts");
		if imgui.begin_popup_context_item():
			if imgui.menu_item_simple("New script"):
				self.prototype["scripts"].append("");
			imgui.end_popup();
		if scripts_open:
			trash = [];
			for i in range(len(self.prototype["scripts"])):
				self.prototype["scripts"][i] = imgui_asset_input(f"script##{i}", "script", self.prototype["scripts"][i]);
				if imgui.begin_popup_context_item():
					if imgui.menu_item_simple("Delete"):
						trash.append(i);
					imgui.end_popup();
			while len(trash) > 0:
				i = trash.pop();
				del self.prototype["scripts"][i];
			imgui.tree_pop();

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
			self.gui_draw_boxes();
			imgui.tree_pop();
		
		imgui_end_column();
		imgui.new_line();

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
			
			if isinstance(event, CanvasManipDrag):
				if event.eeid == None:
					self.selection_context = {};
					return;
			
				match event.signal:
					case CanvasManipDrag.Signal.START:
						if int(abs(event.distance)) > 2:
							self.selection_context = {};
							return;
					
						box = self.search_manip_map(event.eeid);
						edge = aabb_closest_edge(box["aabb"], event.point);
						self.selection_context = {
							"mode": "drag",
							"eeid": event.eeid,
							"box": box,
							"edge": edge
						}

					case CanvasManipDrag.Signal.TICK:
						if self.selection_context != {}:
							point = self.canvas_grid.snap_point(event.point);
							box = self.selection_context["box"];
							edge = self.selection_context["edge"];
							x0, y0, x1, y1 = box["aabb"];
							match edge:
								case Orientation.EAST:
									x1 = point[0];
								case Orientation.NORTH:
									y0 = point[1];
								case Orientation.WEST:
									x0 = point[0];
								case Orientation.SOUTH:
									y1 = point[1];
							if x1 - x0 > 0 and y1 - y0 > 0:
								box["aabb"] = int(x0), int(y0), int(x1), int(y1);
								manip_shape = self.canvas_manipulator.get_shape(event.eeid);
								manip_shape.update(box["aabb"]);
					
					case CanvasManipDrag.Signal.END:
						self.selection_context = {};