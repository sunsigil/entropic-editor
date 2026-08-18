from imgui_bundle import imgui;
import glfw;

from cowtools import *;
from canvas import Canvas, CanvasGrid, CanvasIO;
from assets import *;
from sprites import SpriteBank, EditorSprite;
from input import InputManager;
from editor_gui import *;

class RecipeEditor:
	def __init__(self):	
		self.cell_size = 48
		self.canvas_size = (self.cell_size * 3, self.cell_size * 3);
		self.canvas = Canvas(self.canvas_size[0], self.canvas_size[1], 2);
		self.canvas_io = CanvasIO(self.canvas);
		self.canvas_grid = CanvasGrid(self.canvas, self.cell_size);
	
		self.recipe = None;
		self.selection_context = SelectionContext();
		self.clipboard = Clipboard();
	
	def get_cursor(self):
		if self.canvas_io.is_cursor_in_bounds():
			return self.canvas_grid.transform_point(
				self.canvas_io.get_cursor()
			);
		return None;

	def draw_selector(self):
		recipes = sorted(AssetManager.get_all("recipe"), key=lambda x: x["name"]);
		for recipe in recipes:
			selected = imgui.menu_item_simple(recipe["name"]+f"##{id(recipe)}");
			if selected:
				self.recipe = recipe;
	
	def draw_grid(self):
		self.canvas_io.tick();

		cursor = self.get_cursor();
		if cursor != None:
			x, y = cursor;
			if InputManager.is_pressed(glfw.MOUSE_BUTTON_LEFT):
				self.selection_context.select(int(y * 3 + x), True);

		if InputManager.is_command(glfw.KEY_D):
			self.recipe["inputs"][idx] = "";
		if InputManager.is_command(glfw.KEY_C):
			self.clipboard.copy(self.recipe["inputs"][idx], exclusive=True);
		if InputManager.is_command(glfw.KEY_V):
			if not self.clipboard.is_empty():
				self.recipe["inputs"][idx] = self.clipboard.contents[0];
		
		self.canvas.clear((0, 0, 0));
		self.canvas_grid.draw_lines((128, 128, 128));
		
		if self.recipe != None:
			for y in range(3):
				for x in range(3):
					idx = y * 3 + x;
					item_name = self.recipe["inputs"][idx];
					item = AssetManager.search("item", item_name);
					if item == None:
						continue;
					
					sprite = SpriteBank.search(item["sprite"]);
					self.canvas.draw_image(
						x * self.cell_size + (self.cell_size-sprite.frame_width)/2,
						y * self.cell_size + (self.cell_size-sprite.frame_height)/2,
						sprite.frame_images[0]
					);
		
		if cursor != None:
			self.canvas_grid.draw_cell(cursor, (192, 192, 192));
		if not self.selection_context.is_empty():
			idx = self.selection_context.get_selection(True);
			y = idx // 3;
			x = idx % 3;
			self.canvas_grid.draw_cell((x, y), (255, 255, 255));

		self.canvas.render();
	
	def draw_inspector(self):
		if self.recipe is None:
			return;

		item_name = self.recipe["output"];
		item = AssetManager.search("item", item_name);
		sprite = SpriteBank.search(item["sprite"]) if item != None else SpriteBank.search("null_sprite");

		true_height = sprite.frame_height;
		display_height = self.cell_size * self.canvas.scale;
		scale_factor = display_height / true_height;
		display_width = sprite.frame_width * scale_factor;
		imgui.image(imgui.ImTextureRef(sprite.frame_textures[0]), imgui.ImVec2(display_width, display_height));
		self.recipe["output"] = input_asset("Output", self.recipe["output"], "item");

		self.recipe["oriented"] = input_bool("Oriented", self.recipe["oriented"]);
		
		if not self.selection_context.is_empty():
			imgui.separator();
			idx = self.selection_context.get_selection(True);
			self.recipe["inputs"][idx] = input_asset("Input", self.recipe["inputs"][idx], "item");
	
	def draw(self):
		begin_column("selector", imgui.get_content_region_avail().x * 0.15);
		self.draw_selector();
		end_column();

		begin_column("inputs", imgui.get_content_region_avail().x * 0.5);
		self.draw_grid();
		end_column();

		begin_column("inspector", imgui.get_content_region_avail().x);
		self.draw_inspector();
		end_column();
			
