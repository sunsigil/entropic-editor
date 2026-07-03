from imgui_bundle import imgui;
from PIL import Image;
from pathlib import Path;
import regex as re;
import math;
import glfw;
import copy;

from cowtools import *;
from canvas import Canvas, CanvasGrid, CanvasIO;
from editor_gui import *;
from input import InputManager;
from colours import *;

def highlight(c):
	if value(c) > 224:
		r, g, b = c;
		M = max(r, g, b);
		if M == r:
			return (0, 255, 255);
		if M == g:
			return (255, 0, 255);
		if M == b:
			return (255, 255, 0);
	return (255, 255, 255);

class PalettePipeline:
	def __init__(self, palette):
		self.colours = list(tuple(c["rgb888"]) for c in palette["colours"]);
		self.stages = [];

	def stage(self, function):
		self.stages.append(function);

	def bake(self):
		pipeline = [list(self.colours)];
		for stage in self.stages:
			data = [stage(c) for c in pipeline[-1]];
			pipeline.append(data);
		return pipeline;

class PaletteViewer:
	def __init__(self):
		self.path = None;
		self.palette = None;

		self.cursor = 0;
		self.clipboard = None;

		self.tile_size = 32;
		self.max_cols = 8;
		self.views = [];
	
	def get_cols(self):
		return min(len(self.palette["colours"]), self.max_cols);

	def get_rows(self):
		if self.get_cols() == 0:
			return 0;
		return math.ceil(len(self.palette["colours"]) / self.get_cols());
	
	def make_view(self):
		if len(self.palette["colours"]) == 0:
			return None;
		canvas = Canvas(self.get_cols() * self.tile_size, self.get_rows() * self.tile_size, 1);
		canvas_grid = CanvasGrid(canvas, self.tile_size);
		canvas_io = CanvasIO(canvas);
		return (canvas, canvas_grid, canvas_io);

	def acquire_view(self):
		if len(self.views) == 0:
			return self.make_view();
		return self.views.pop();

	def release_view(self, view):
		self.views.append(view);
	
	def draw_view(self, view, colours, name=""):
		if imgui.collapsing_header(name):
			if view == None:
				return;
		
			canvas, canvas_grid, canvas_io = view;

			canvas.clear((0, 0, 0, 0));
			for row in range(self.get_rows()):
				for col in range(self.get_cols()):
					idx = row * self.get_cols() + col;
					if idx < len(colours):
						canvas_grid.draw_cell((col, row), colours[idx], fill=True);
			
			row = self.cursor // self.get_cols();
			col = self.cursor % self.get_cols();
			canvas_grid.draw_cell((col, row), highlight(colours[self.cursor]));
			canvas.render();

			canvas_io.tick();
			if canvas_io.cursor_in_bounds() and InputManager.is_pressed(glfw.MOUSE_BUTTON_LEFT):
				point = canvas_io.get_cursor();
				point = canvas_grid.transform_point(point);
				self.cursor = int(point[1] * self.get_cols() + point[0]);
	
	def gui_draw_selector(self):
		palettes = sorted(AssetManager.get_all("palette"), key=lambda x: x["name"]);

		for palette in palettes:
			selected = imgui.menu_item_simple(palette["name"]);

			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("New"):
					AssetManager.get_document("palette").spawn_entry();
					imgui.close_current_popup();
				if imgui.menu_item_simple("Delete"):
					AssetManager.get_document("palette").delete_entry(palette);
					imgui.close_current_popup();
				imgui.end_popup();
			
			if selected:
				self.palette = palette;
	
	def draw(self):
		begin_column("selector", imgui.get_content_region_avail().x * 0.1);
		palette_last = self.palette;
		self.gui_draw_selector();
		if self.palette != palette_last:
			self.cursor = 0;
		end_column();

		begin_column("views", self.max_cols * self.tile_size * 1.1);
		if self.palette != None:
			pipeline = PalettePipeline(self.palette);

			names = ["Original"];
			pipeline.stage(restrict_precision);
			names.append("RGB565");
			pipeline.stage(apply_gamma);
			names.append("Gamma");
			stages = pipeline.bake();

			self.views = [];
			views = [self.acquire_view() for stage in stages];
			for (idx, stage) in enumerate(stages):
				view = views[idx];
				self.draw_view(view, stage, names[idx]);
			for view in views:
				self.release_view(view);
		
			self.cursor = clamp(self.cursor, 0, len(self.palette["colours"])-1);
		end_column();

		begin_column("edit", imgui.get_content_region_avail().x);
		if self.palette != None:
			if len(self.palette["colours"]) > 0:
				colour = self.palette["colours"][self.cursor];
				imgui.push_id(str(id(colour)));

				_, colour["name"] = imgui.input_text("Name", colour["name"]);
				
				r, g, b = colour["rgb888"];
				_, (r, g, b) = imgui.color_edit3("RGB888", (r/255, g/255, b/255));
				colour["rgb888"] = [int(r*255), int(g*255), int(b*255)];

				if InputManager.is_command(glfw.KEY_V):
					if self.clipboard != None:
						r, g, b = self.clipboard["rgb888"];
						colour["rgb888"] = [r, g, b];

				imgui.pop_id();
			
			if imgui.button("New colour"):
				self.palette["colours"].append({
					"name": "Untitled",
					"rgb888": [255, 255, 255]
				});
		
			if InputManager.is_command(glfw.KEY_C):
				self.clipboard = copy.copy(colour);
		end_column();

			
				
					

