from imgui_bundle import imgui;
import glfw;
import math;

from canvas import *;
from assets import AssetManager;
from sprites import SpriteBank;
from input import InputManager;
from editor_gui import *;
from geometry import *;
import scenes.entities;

# Paints entities the way the tilemap editor paints tiles: pick a prototype
# from the palette, then click or drag over the canvas to place one per
# snapped spot. Shift erases, alt picks the prototype under the cursor
class FoliageEditor:
	def __init__(self, parent):
		self.parent = parent;
		self.entities = None;

		# never gets shapes, so it only yields view drags for panning
		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(self.parent.canvas_io, self.event_queue);

		self.search = "";
		self.prototype = None;
		self.cursor = None;
		self.paint_last = None;

	def on_load_scene(self):
		self.entities = self.parent.scene["entities"];
		self.canvas_manip.clear();
		self.paint_last = None;

	def validate(self):
		# the scene's list can be swapped out under us by an undo
		self.entities = self.parent.scene["entities"];
		if self.prototype != None and self.prototype not in AssetManager.get_all("prototype"):
			self.prototype = None;

	def draw_palette(self):
		_, self.search = imgui.input_text("Search", self.search);
		prototypes = sorted(AssetManager.get_all("prototype"), key=lambda x: x["name"]);
		prototypes = [x for x in prototypes if self.search in x["name"]];

		wdw_w = imgui.get_content_region_avail().x;
		cols = max(int(wdw_w // 72), 1);
		rows = int(math.ceil(len(prototypes) / cols));

		i = 0;
		for r in range(rows):
			for c in range(cols):
				if i < len(prototypes):
					prototype = prototypes[i];
					sprite = SpriteBank.search(prototype["sprite"]);
					imgui.begin_group();
					tint = (0.5, 0.5, 0.5, 1) if prototype is self.prototype else (1, 1, 1, 1);
					if imgui.image_button(f"##{id(prototype)}", imgui.ImTextureRef(sprite.frame_textures[0]), (64, 64), tint_col=tint):
						self.prototype = prototype;
					imgui.text(prototype["name"][:10]);
					imgui.end_group();
					imgui.same_line();
				i += 1;
			imgui.new_line();

	def draw_gui(self):
		if self.entities == None:
			return;

		imgui.text(f"Prop: {self.prototype["name"] if self.prototype != None else "none"}");
		imgui.text_disabled("click/drag: place, shift: erase, alt: pick, right drag: pan");
		self.draw_palette();

	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CanvasManipViewDrag):
				CanvasManipulator.default_view_drag_handler(self.parent.canvas, event);

	def get_place_position(self):
		position = self.cursor;
		if self.parent.snap:
			position = self.parent.canvas_grid.snap_point(position);
		return [int(position[0]), int(position[1])];

	# topmost entity under the point, optionally only of one prototype
	def find_entity(self, point, prototype_name=None):
		hits = [
			x for x in self.entities
			if (prototype_name == None or x["prototype"] == prototype_name)
			and aabb_contains_point(scenes.entities.get_aabb(x), point)
		];
		if len(hits) == 0:
			return None;
		return max(hits, key=scenes.entities.get_body_key);

	def is_occupied(self, position):
		return any(x["prototype"] == self.prototype["name"] and x["position"] == position for x in self.entities);

	def edit(self):
		if self.cursor == None:
			self.paint_last = None;
			return;

		if InputManager.is_held(glfw.KEY_LEFT_ALT):
			self.paint_last = None;
			if InputManager.is_pressed(glfw.MOUSE_BUTTON_LEFT):
				entity = self.find_entity(self.cursor);
				if entity != None:
					self.prototype = AssetManager.search("prototype", entity["prototype"]);
			return;

		if self.prototype == None:
			return;

		if not InputManager.is_held(glfw.MOUSE_BUTTON_LEFT):
			self.paint_last = None;
			return;

		if InputManager.is_held(glfw.KEY_LEFT_SHIFT):
			entity = self.find_entity(self.cursor, self.prototype["name"]);
			if entity != None:
				self.parent.trash.trash_item(self.entities, entity);
				self.parent.trash.flush();
			return;

		position = self.get_place_position();
		if position != self.paint_last and not self.is_occupied(position):
			scenes.entities.spawn(self.parent.scene, self.prototype["name"], position);
		self.paint_last = position;

	def draw_canvas(self):
		if self.prototype == None or self.cursor == None:
			return;

		colour = (255, 255, 255);
		if InputManager.is_held(glfw.KEY_LEFT_ALT):
			colour = (128, 255, 128);
		elif InputManager.is_held(glfw.KEY_LEFT_SHIFT):
			colour = (255, 128, 128);

		x, y = self.get_place_position();
		sprite = SpriteBank.search(self.prototype["sprite"], safe=False);
		if sprite != None and not InputManager.is_held(glfw.KEY_LEFT_SHIFT):
			dx, dy = self.prototype["sprite_offset"];
			self.parent.canvas.draw_image(x+dx, y+dy, sprite.frame_images[0]);
		ghost = {"prototype": self.prototype["name"], "position": [x, y]};
		self.parent.canvas.draw_aabb(scenes.entities.get_aabb(ghost), colour);

	def tick(self):
		self.validate();

		self.canvas_manip.tick();
		self.handle_events();

		if self.parent.canvas_io.is_cursor_in_bounds():
			self.cursor = self.parent.canvas_io.get_cursor();
		else:
			self.cursor = None;

		self.edit();
