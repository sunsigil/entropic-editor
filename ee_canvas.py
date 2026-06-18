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
		imgui.image(imgui.ImTextureRef(self.texture), imgui.ImVec2(self.width * self.scale, self.height * self.scale));

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
		if self.cursor == None:
			return False;
		x0, y0 = self._transform(0, 0);
		x1, y1 = self._transform(self.canvas.width, self.canvas.height);
		return aabb_contains_point((x0, y0, x1, y1), self.cursor);

	def in_bounds_cursor(self):
		if self.cursor == None:
			return None;
		x0, y0 = self._transform(0, 0);
		x1, y1 = self._transform(self.canvas.width, self.canvas.height);
		if self.cursor_in_bounds():
			return self.cursor;
		return aabb_closest_point((x0, y0, x1, y1), self.cursor);

class CanvasGrid:
	def __init__(self, canvas, size):
		self.canvas = canvas;
		self.size = int(size);

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
	def __init__(self, eeid, aabb):
		x0, y0, x1, y1 = aabb;
		self.aabb = (x0, y0, x1, y1);
		self.eeid = eeid;

	def distance(self, point):
		return aabb_point_sdf(self.aabb, point);

	def update(self, aabb):
		x0, y0, x1, y1 = aabb;
		self.aabb = (x0, y0, x1, y1);

class CanvasManipSegment:
	def __init__(self, eeid, segment):
		self.segment = segment;
		self.eeid = eeid;

	def distance(self, point):
		# SDF radius of 4
		return segment_point_sdf(self.segment, point)-4;

	def update(self, segment):
		self.segment = segment;

class CanvasManipClick:
	def __init__(self, eeid, point, distance=None):
		self.eeid = eeid;
		self.point = point;
		self.distance = distance;

class CanvasManipDrag:
	class Signal(Enum):
		START = 0,
		TICK = 1,
		END = 2
	def __init__(self, eeid, signal, point, distance=None):
		self.eeid = eeid;
		self.signal = signal;
		self.point = point;
		self.distance = distance;

class CanvasManipulator:
	def __init__(self, canvas_io, event_queue):
		self.canvas_io = canvas_io;
		self.event_queue = event_queue;

		self.shapes = [];
		self.eeid = iter(EEID());
		
		self.clicked_point = None;
		self.clicked_eeid = None;
		self.drag_started = False;
	
	def _get_by_eeid(self, eeid):
		for shape in self.shapes:
			if shape.eeid == eeid:
				return shape;
		return None;

	def _get_by_point(self, point):
		min_dist = math.inf;
		min_shape = None;
		for shape in self.shapes:
			dist = shape.distance(point);
			if dist <= 2 and abs(dist) < min_dist:
				min_dist = abs(dist);
				min_shape = shape;
		return min_shape;

	def clear(self):
		self.shapes = [];
		self.eeid = iter(EEID());
		
		self.clicked_point = None;
		self.clicked_eeid = None;
		self.drag_started = False;

	def register_aabb(self, aabb):
		eeid = next(self.eeid);
		shape = CanvasManipRect(eeid, aabb);
		self.shapes.append(shape);
		return eeid;

	def register_segment(self, segment):
		eeid = next(self.eeid);
		shape = CanvasManipSegment(eeid, segment);
		self.shapes.append(shape);
		return eeid;

	def get_shape(self, eeid):
		return self._get_by_eeid(eeid);

	def delete_shape(self, eeid):
		trash = [];
		for shape in self.shapes:
			if shape.eeid == eeid:
				trash.append(shape);
		for t in trash:
			self.shapes.remove(t);

	def tick(self):
		cursor = self.canvas_io.in_bounds_cursor();

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
		
		else:
			if InputManager.is_pressed(glfw.MOUSE_BUTTON_LEFT):
				self.clicked_point = cursor;
				shape = self._get_by_point(cursor);
				eeid = shape.eeid if shape != None else None;
				distance = shape.distance(self.clicked_point) if shape != None else None;
				self.event_queue.append(CanvasManipClick(eeid, cursor, distance));
				self.clicked_eeid = eeid;
		
			if InputManager.is_held(glfw.MOUSE_BUTTON_LEFT) and self.clicked_point != None:
				shape = self._get_by_eeid(self.clicked_eeid);
				distance = shape.distance(self.clicked_point) if shape != None else None;

				if not self.drag_started:
					movement = point_point_dist(cursor, self.clicked_point);
					if movement >= 2:
						self.event_queue.append(CanvasManipDrag(self.clicked_eeid, CanvasManipDrag.Signal.START, self.clicked_point, distance));
						self.drag_started = True;
				else:
					self.event_queue.append(CanvasManipDrag(self.clicked_eeid, CanvasManipDrag.Signal.TICK, cursor, distance));
					
		
		

		
