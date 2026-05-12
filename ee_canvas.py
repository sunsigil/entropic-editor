from enum import Flag, auto;
from imgui_bundle import imgui;
from PIL import Image, ImageDraw;
import glfw;

from ee_cowtools import *;
from ee_input import InputManager;

class Canvas:
	def __init__(self, width, height, scale=1, origin=(0, 0)):
		self.width = width;
		self.height = height;
		self.scale = scale;
		self.origin = origin;

		self.image = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0));
		self.texture = make_texture(self.image.tobytes(), width, height);
		self.draw = ImageDraw.Draw(self.image);
		self.draw_flags = ();
	
		self.position = None;
	
	def _transform(self, x, y):
		x += self.origin[0];
		y += self.origin[1];
		return x, y;
	
	def _in_bounds(self, x, y):
		return (
			x >= 0 and x < self.width and
			y >= 0 and y < self.height
		);

	def clear(self, c):
		self.draw.rectangle((0, 0, self.width, self.height), fill=c);

	def draw_pixel(self, x, y, c):
		x, y = self._transform(x, y);
		self.draw.point((x, y), fill=c);
	
	def draw_aabb(self, aabb, c, fill=False):
		x0, y0, x1, y1 = aabb;
		x0, y0 = self._transform(x0, y0);
		x1, y1 = self._transform(x1, y1);
		w, h = x1-x0, y1-y0;
		if w <= 0 or h <= 0:
			return;
		if fill:
			self.draw.rectangle((x0, y0, x1, y1), fill=c);
		else:
			self.draw.rectangle((x0, y0, x1, y1), outline=c);

	def draw_line(self, x0, y0, x1, y1, c):
		x0, y0 = self._transform(x0, y0);
		x1, y1 = self._transform(x1, y1);
		self.draw.line((x0, y0, x1, y1), fill=c);

	def draw_circle(self, x, y, r, c):
		x, y = self._transform(x, y);
		self.draw.circle((x, y), r, outline=c);
	
	def draw_image(self, x, y, image):
		x, y = self._transform(x, y);
		self.image.paste(image, (int(x), int(y)), mask=image);
	
	def draw_text(self, xy, text, s, c):
		x, y = xy;
		xy = self._transform(x, y);
		self.draw.text(xy, str(text), font_size=s, stroke_fill=c);
	
	def draw_guides(self, c):
		ox, oy = self.origin;
		w, h = self.width, self.height;
		self.draw_line(-ox, 0, w-ox, 0, c);
		self.draw_line(0, -oy, 0, h-oy, c);
	
	def render(self):
		self.position = imgui.get_cursor_screen_pos();
		glBindTexture(GL_TEXTURE_2D, self.texture);
		glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE, self.image.tobytes());
		imgui.image(self.texture, (self.width * self.scale, self.height * self.scale));

class CanvasIO:
	def __init__(self, canvas):
		self.canvas = canvas;
		self.cursor = None;
	
	def _transform(self, x, y):
		x -= self.canvas.origin[0];
		y -= self.canvas.origin[1];
		return x, y;
	
	def tick(self):
		if not self.canvas.position is None:
			x, y = InputManager.get_imgui_cursor() - self.canvas.position;
			x, y = x / self.canvas.scale, y / self.canvas.scale;
			x, y = self._transform(x, y);
			self.cursor = x, y;

	def get_cursor(self):
		return self.cursor;

	def cursor_in_bounds(self):
		if self.cursor != None:
			x0, y0 = self._transform(0, 0);
			x1, y1 = self._transform(self.canvas.width, self.canvas.height);
			return aabb_contains_point((x0, y0, x1, y1), self.cursor);
		return False;

	def in_bounds_cursor(self):
		if self.cursor == None:
			return False;
		x0, y0 = self._transform(0, 0);
		x1, y1 = self._transform(self.canvas.width, self.canvas.height);
		if self.cursor_in_bounds():
			return self.cursor;
		return aabb_closest_point((x0, y0, x1, y1), self.cursor);

class CanvasGrid:
	def __init__(self, canvas, size):
		self.canvas = canvas;
		self.size = int(size);
		self.rows = self.canvas.height // self.size;
		self.columns = self.canvas.width // self.size;

	def transform_point(self, point):
		x, y = point;
		x, y = x // self.size, y // self.size;
		return x, y;

	def untransform_point(self, point):
		x, y = point;
		x, y = x * self.size, y * self.size;
		return x, y;

	def transform_aabb(self, aabb):
		x0, y0, x1, y1 = aabb;
		x0y0, x1y1 = self.transform_point((x0, y0)), self.transform_point((x1, y1));
		x0, y0 = x0y0;
		x1, y1 = x1y1;
		return x0, y0, x1, y1;

	def untransform_aabb(self, aabb):
		x0, y0, x1, y1 = aabb;
		x0y0, x1y1 = self.untransform_point((x0, y0)), self.untransform_point((x1, y1));
		x0, y0 = x0y0;
		x1, y1 = x1y1;
		return x0, y0, x1, y1;

	def snap_point(self, point):
		return self.untransform_point(self.transform_point(point));

	def snap_aabb(self, aabb):
		return self.untransform_aabb(self.transform_aabb(aabb));

	def draw_lines(self, colour):
		ox, oy = self.canvas.origin;
		x0 = -math.ceil(ox/self.size)*self.size;
		y0 = -math.ceil(oy/self.size)*self.size;
		x1 = x0 + self.canvas.width + self.size;
		y1 = y0 + self.canvas.height + self.size;
		for y in range(y0+self.size, y1, self.size):
			self.canvas.draw_line(x0, y, x1, y, colour);
		for x in range(x0+self.size, x1, self.size):
			self.canvas.draw_line(x, y0, x, y1, colour);

	def draw_cell(self, point, colour, fill=False):
		point = self.untransform_point(point);
		x0, y0 = point;
		x1, y1 = x0 + self.size, y0 + self.size;
		self.canvas.draw_aabb((x0, y0, x1, y1), colour, fill);

class CanvasManipRect:
	def __init__(self, eeid, aabb, fill=False):
		x0, y0, x1, y1 = aabb;
		self.aabb = (x0, y0, x1, y1);
		self.eeid = eeid;
		self.fill = fill;

	def distance(self, point):
		if self.fill:
			if aabb_contains_point(self.aabb, point):
				return 0;
		near = aabb_closest_point(self.aabb, point);
		return point_point_dist(point, near);

	def update(self, aabb):
		x0, y0, x1, y1 = aabb;
		self.aabb = (x0, y0, x1, y1);

class CanvasManipClick:
	def __init__(self, eeid, point):
		self.eeid = eeid;
		self.point = point;

class CanvasManipDrag:
	class Signal(Enum):
		START = 0,
		TICK = 1,
		END = 2
	def __init__(self, eeid, signal, point, ):
		self.eeid = eeid;
		self.signal = signal;
		self.point = point;

class CanvasManipulator:
	def __init__(self, canvas_io):
		self.canvas_io = canvas_io;

		self.shapes = [];
		self.eeid = iter(EEID());

		self.event_queue = [];
		self.click_callback = None;
		self.drag_callback = None;

		self.clicked_point = None;
		self.clicked_eeid = None;
		self.drag_started = False;
	
	def _get_by_eeid(self, eeid):
		for shape in self.shapes:
			if shape.eeid == eeid:
				return shape;
		return None;

	def _get_by_point(self, point):
		for shape in self.shapes:
			dist = shape.distance(point);
			if dist <= 1:
				return shape;
		return None;

	def get(self, eeid):
		return self._get_by_eeid(eeid);

	def clear(self):
		self.shapes = [];
		self.event_queue = [];
		self.eeid = iter(EEID());
		self.action_context = {};

	def register(self, aabb, fill=False):
		eeid = next(self.eeid);
		shape = CanvasManipRect(eeid, aabb, fill=fill);
		self.shapes.append(shape);
		return eeid;

	def tick(self):
		cursor = self.canvas_io.in_bounds_cursor();

		if InputManager.is_pressed(glfw.MOUSE_BUTTON_LEFT) and self.canvas_io.cursor_in_bounds():
			self.clicked_point = cursor;
			shape = self._get_by_point(cursor);
			eeid = shape.eeid if shape != None else None;
			self.event_queue.append(CanvasManipClick(eeid, cursor));
			self.clicked_eeid = eeid;
		
		if InputManager.is_held(glfw.MOUSE_BUTTON_LEFT) and self.clicked_eeid != None:
			if self.drag_started:
				self.event_queue.append(CanvasManipDrag(self.clicked_eeid, CanvasManipDrag.Signal.TICK, cursor));
			else:
				movement = point_point_dist(cursor, self.clicked_point);
				if movement >= 2:
					self.event_queue.append(CanvasManipDrag(self.clicked_eeid, CanvasManipDrag.Signal.START, self.clicked_point));
					self.drag_started = True;
		
		cancel = (
			InputManager.is_released(glfw.MOUSE_BUTTON_LEFT) or
			not self.canvas_io.cursor_in_bounds()
		);

		if cancel:
			if self.drag_started:
				self.event_queue.append(CanvasManipDrag(self.clicked_eeid, CanvasManipDrag.Signal.END, cursor));
			self.clicked_point = None;
			self.clicked_eeid = None;
			self.drag_started = False;

		for event in self.event_queue:
			if isinstance(event, CanvasManipClick) and self.click_callback != None:
				self.click_callback(event);
			elif isinstance(event, CanvasManipDrag) and self.drag_callback != None:
				self.drag_callback(event);
		self.event_queue = [];
