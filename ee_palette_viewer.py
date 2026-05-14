from imgui_bundle import imgui;
from PIL import Image;
from pathlib import Path;
import regex as re;
import math;

from ee_cowtools import *;
from ee_canvas import Canvas, CanvasGrid;
from ee_imgui import *;

def restrict_precision(c):
	r, g, b = c;
	r = round((r / 255) * 31);
	g = round((g / 255) * 63);
	b = round((b / 255) * 31);
	r = round((r / 31) * 255);
	g = round((g / 63) * 255);
	b = round((b / 31) * 255);
	return (r, g, b);

def apply_gamma(c):
	r, g, b = c;
	Gr, Gg, Gb = 1.2, 1.2, 1.6;
	rf, gf, bf = r/255, g/255, b/255;
	rf, gf, bf = rf ** (1/Gr), gf ** (1/Gg), bf ** (1/Gb);
	return (int(rf*255), int(gf*255), int(bf*255));

def hue(c):
	r, g, b = c;
	r /= 255;
	g /= 255;
	b /= 255;

	lmax = max(r, g, b);
	lmin = min(r, g, b);
	range = lmax-lmin;
	if range <= 0:
		return 0;
	
	if r >= g and r >= b:
		return (g-b)/range;
	if g >= r and g >= b:
		return 2 + (b-r)/range;
	if b >= r and b >= g:
		return 4 + (r-g)/range;

def saturation(c):
	m = min(c);
	M = max(c);
	return (M-m) / M if M != 0 else 0;

def value(c):
	return math.sqrt(0.299*c[0]**2 + 0.587*c[1]**2 + 0.114*c[2]**2);

class Palette:
	def __init__(self, text):
		self.colours = [];
		lines = text.splitlines();
		for line in lines:
			tokens = re.split(r"[\s\t]+", line.strip(), maxsplit=3);
			match tokens:
				case r, g, b, name:
					self.colours.append(((int(r), int(g), int(b)), name));
		self.colours.sort(key=lambda c: (hue(c[0]), value(c[0]), saturation(c[0])));

class PalettePipeline:
	def __init__(self, colours):
		self.colours = list(colours);
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
		self.tile_size = 32;
	
		self.restrict_precision = False;
		self.apply_gamma = False;
		self.views = [];
	
	def make_view(self):
		N = len(self.palette.colours);
		cols = min(N, 16);
		rows = math.ceil(N / cols);
		canvas = Canvas(cols * self.tile_size, rows * self.tile_size, 1);
		canvas_grid = CanvasGrid(canvas, self.tile_size);
		return (canvas, canvas_grid);

	def acquire_view(self):
		if len(self.views) == 0:
			return self.make_view();
		view = self.views[-1];
		self.views.pop();
		return view;

	def release_view(self, view):
		self.views.append(view);
	
	def draw_view(self, view, colours, name=None):
		canvas, canvas_grid = view;
		canvas.clear((0, 0, 0, 0));
		for row in range(canvas_grid.rows):
			for col in range(canvas_grid.columns):
				idx = row * canvas_grid.columns + col;
				if idx < len(colours):
					canvas_grid.draw_cell((col, row), colours[idx], fill=True);
		canvas.render();
		if name != None:
			imgui.same_line();
			imgui.text(name);
	
	def draw(self):
		if self.path == None or not self.path.suffix == ".gpl":
			self.path = Path(imgui_path_input(id(self), self.path, "*.gpl"));
		
		elif self.palette == None:
			file = open(self.path, "r");
			text = file.read();
			self.palette = Palette(text);
		
		else:
			_, self.restrict_precision = imgui.checkbox("Restrict Precision", self.restrict_precision);
			imgui.same_line();
			_, self.apply_gamma = imgui.checkbox("Apply Gamma", self.apply_gamma);

			pipeline = PalettePipeline([c[0] for c in self.palette.colours]);
			names = ["Original"];
			if self.restrict_precision:
				pipeline.stage(restrict_precision);
				names.append("RGB565");
			if self.apply_gamma:
				pipeline.stage(apply_gamma);
				names.append("Gamma");
			stages = pipeline.bake();

			views = [self.acquire_view() for stage in stages];
			for (idx, stage) in enumerate(stages):
				view = views[idx];
				self.draw_view(view, stage, names[idx]);
			for view in views:
				self.release_view(view);

			
				
					

