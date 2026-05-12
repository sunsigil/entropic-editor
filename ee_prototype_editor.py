from imgui_bundle import imgui;
import glfw;
from enum import Enum;

from ee_cowtools import *;
from ee_canvas import *
from ee_assets import *;
from ee_sprites import SpriteBank;
from ee_input import InputManager;
from ee_imgui import *;

class PrototypeEditor:
	def __init__(self):
		self.canvas_size = (256, 256);
		self.tile_size = 16;

		self.canvas = Canvas(self.canvas_size[0], self.canvas_size[1], scale=2, origin=(128, 128));
		self.canvas_io = CanvasIO(self.canvas);
		self.canvas_grid = CanvasGrid(
			self.canvas,
			self.tile_size
		);

		self.canvas_manipulator = CanvasManipulator(self.canvas_io);
		self.canvas_manipulator.click_callback = self.click_callback;
		self.canvas_manipulator.drag_callback = self.drag_callback;
	
		self.manip_map = {};
		self.selection_context = {};
		self.load_prototype(AssetManager.get_first("prototype"));
	
	def load_prototype(self, prototype):
		self.prototype = prototype;
		if prototype != None:
			sprite = SpriteBank.get(self.prototype["sprite"]);
			self.canvas.origin = (128-sprite.frame_width//2, 128-sprite.frame_height//2);

			self.canvas_manipulator.clear();
			self.manip_map = {};
			for box in self.prototype["boxes"]:
				eeid = self.canvas_manipulator.register(box["aabb"]);
				self.manip_map[eeid] = id(box);
	
	def search_manip_map(self, eeid):
		if self.prototype == None:
			return None;
		py_id = self.manip_map[eeid];
		for box in self.prototype["boxes"]:
			if id(box) == py_id:
				return box;
		return None;
	
	def click_callback(self, click: CanvasManipClick):
		if click.eeid == None:
			self.selection_context = {};
			return;
	
		self.selection_context = {
			"mode" : click,
			"eeid": click.eeid
		};
	
	def drag_callback(self, drag: CanvasManipDrag):
		if drag.eeid == None:
			self.selection_context = {};
			return;
	
		match drag.signal:
			case CanvasManipDrag.Signal.START:	
				box = self.search_manip_map(drag.eeid);
				edge = aabb_closest_edge(box["aabb"], drag.point);
				self.selection_context = {
					"mode": "drag",
					"eeid": drag.eeid,
					"box": box,
					"edge": edge
				}

			case CanvasManipDrag.Signal.TICK:
				point = self.canvas_grid.snap_point(drag.point);
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
					manip_shape = self.canvas_manipulator.get(drag.eeid);
					manip_shape.update(box["aabb"]);
			
			case CanvasManipDrag.Signal.END:
				self.selection_context = {};
				pass;
	
	def gui_draw_selector(self):
		prototype_last = self.prototype;
		self.prototype = imgui_asset_selector(id(self.prototype), "prototype", self.prototype);
		
		if self.prototype != prototype_last:
			self.load_prototype(self.prototype);
	
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
	
	def draw(self):
		self.gui_draw_selector();

		self.canvas.clear((128, 128, 128));
		self.canvas_grid.draw_lines((64, 64, 64));
		if self.prototype != None:
			sprite = SpriteBank.get(self.prototype["sprite"]);
			self.canvas.draw_image(0, 0, sprite.frame_images[0]);
			self.canvas_draw_boxes();
		self.canvas.render();

		if imgui.tree_node("Boxes"):
			self.gui_draw_boxes();
			imgui.tree_pop();

		self.canvas_io.tick();
		self.canvas_manipulator.tick();