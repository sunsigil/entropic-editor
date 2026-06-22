from enum import Flag, auto;
from imgui_bundle import imgui;
from PIL import Image, ImageDraw;
import glfw;

from ee_cowtools import *;
from ee_input import InputManager;
from ee_geometry import *;
from ee_imgui import *;

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
		self.has_mouse = False;
	
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
	
	def render(self, gui_id=None):
		self.position = imgui.get_cursor_screen_pos();
		glBindTexture(GL_TEXTURE_2D, self.texture);
		glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE, self.image.tobytes());
		imgui.image(imgui.ImTextureRef(self.texture), imgui.ImVec2(self.width * self.scale, self.height * self.scale));
		EEGUIContextMenu.ping(gui_id);
		self.has_mouse = imgui.is_item_hovered();

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

	def is_cursor_in_bounds(self):
		if self.cursor == None:
			return False;
		x0, y0 = self._transform(0, 0);
		x1, y1 = self._transform(self.canvas.width, self.canvas.height);
		return aabb_contains_point((x0, y0, x1, y1), self.cursor) and self.canvas.has_mouse;

	def get_bounded_cursor(self):
		if self.cursor == None:
			return None;
		x0, y0 = self._transform(0, 0);
		x1, y1 = self._transform(self.canvas.width, self.canvas.height);
		if self.is_cursor_in_bounds():
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
	def __init__(self, aabb):
		x0, y0, x1, y1 = aabb;
		self.aabb = x0, y0, x1, y1;

	def distance(self, point):
		return aabb_point_sdf(self.aabb, point);

	def delta(self, point):
		return self.aabb[0] - point[0], self.aabb[1] - point[1];

	def update(self, aabb):
		x0, y0, x1, y1 = aabb;
		self.aabb = x0, y0, x1, y1;

class CanvasManipSegment:
	def __init__(self, segment, radius=4):
		self.segment = segment;
		self.radius = radius;

	def distance(self, point):
		return segment_point_sdf(self.segment, point)-self.radius;

	def delta(self, point):
		return self.segment[0][0] - point[0], self.segment[0][1] - point[1];

	def update(self, segment):
		self.segment = segment;

class CanvasManipPoint:
	def __init__(self, point, radius=4):
		self.point = point;
		self.radius = radius;

	def distance(self, point):
		return point_point_dist(self.point, point)-self.radius;

	def delta(self, point):
		return self.point[0] - point[0], self.point[1] - point[1];

	def update(self, point):
		self.point = point;

class CanvasManipClick:
	def __init__(self, eeid, point, delta=None, distance=None):
		self.eeid = eeid;
		self.point = point;
		self.delta = delta;
		self.distance = distance;

class CanvasManipDrag:
	class Signal(Enum):
		START = 0,
		TICK = 1,
		END = 2
	def __init__(self, signal, eeid, start, point, delta=None, distance=None):
		self.eeid = eeid;
		self.signal = signal;
		self.start = start;
		self.point = point;
		self.delta = delta;
		self.distance = distance;

class CanvasManipRecord:
	def __init__(self, object, shape, eeid):
		self.object = object;
		self.shape = shape;
		self.eeid = eeid;
class CanvasManipRegistry:
	def __init__(self, objects=[], shapes=[], eeids=[]):
		self.records = [];
		for i in range(len(objects)):
			self.register(objects[i], shapes[i], eeids[i] if eeids != [] else None);
	
	def clear(self):
		self.update([], []);
	
	def register(self, object, shape, eeid=None):
		existing = next((x for x in self.records if x.object == object), None);
		if existing:
			existing.shape = shape;
		else:
			self.records.append(CanvasManipRecord(
				object,
				shape,
				eeid
			));
	
	def update(self, objects, shapes):
		for i in range(len(objects)):
			self.register(objects[i], shapes[i]);
		trash = [];
		for i in range(len(self.records)):
			if not self.records[i].object in objects:
				trash.append(i);
		process_trash(self.records, trash, True);
	
	def search(self, eeid):
		for record in self.records:
			if record.eeid == eeid:
				return record.object;

class CanvasManipulator:
	def __init__(self, canvas_io, event_queue):
		self.canvas_io = canvas_io;
		self.event_queue = event_queue;

		self.eeid = iter(EEID());
		self.shapes = {};

		self.clicked_point = None;
		self.clicked_eeid = None;
		self.clicked_delta = None;
		self.clicked_distance = None;

		self.dragging = False;

	def _spatial_search(self, point):
		min_dist = math.inf;
		min_eeid = None;
		for eeid,shape in self.shapes.items():
			dist = shape.distance(point);
			if dist <= 2 and abs(dist) < min_dist:
				min_dist = abs(dist);
				min_eeid = eeid;
		return min_eeid;

	def clear(self):
		self.eeid = iter(EEID());
		self.shapes = {};
		
		self.clicked_point = None;
	
	def synchronize(self, registry: CanvasManipRegistry):
		canon_eeids = set();
		for record in registry.records:
			if record.eeid == None:
				record.eeid = next(self.eeid);
			self.shapes[record.eeid] = record.shape;
			canon_eeids.add(record.eeid);
		invalid_eeids = [eeid for eeid in self.shapes if eeid not in canon_eeids];
		for eeid in invalid_eeids:
			del self.shapes[eeid];
	
	def search(self, eeid):
		if eeid in self.shapes:
			return self.shapes[eeid];
		return None;

	def tick(self):
		cursor = self.canvas_io.get_bounded_cursor();

		cancel = (
			InputManager.is_released(glfw.MOUSE_BUTTON_LEFT) or
			not self.canvas_io.is_cursor_in_bounds()
		);

		if cancel:
			if self.dragging:
				self.event_queue.append(CanvasManipDrag(CanvasManipDrag.Signal.END, self.clicked_eeid, self.clicked_point, self.canvas_io.get_bounded_cursor()));
			self.dragging = False;
			
			self.clicked_point = None;
		
		else:
			if InputManager.is_pressed(glfw.MOUSE_BUTTON_LEFT):
				self.clicked_point = cursor;
				self.clicked_eeid = self._spatial_search(cursor);
				if self.clicked_eeid == None:
					self.event_queue.append(CanvasManipClick(self.clicked_eeid, self.clicked_point));
					return;
				shape = self.shapes[self.clicked_eeid];
				self.clicked_delta = shape.delta(cursor);
				self.clicked_distance = shape.distance(cursor);
				self.event_queue.append(CanvasManipClick(self.clicked_eeid, self.clicked_point, self.clicked_delta, self.clicked_distance));
		
			if InputManager.is_held(glfw.MOUSE_BUTTON_LEFT) and self.clicked_point != None:
				if not self.dragging:
					movement = point_point_dist(cursor, self.clicked_point);
					if movement >= 2:
						self.event_queue.append(CanvasManipDrag(CanvasManipDrag.Signal.START, self.clicked_eeid, self.clicked_point, cursor, self.clicked_delta, self.clicked_distance));
						self.dragging = True;
				else:
					self.event_queue.append(CanvasManipDrag(CanvasManipDrag.Signal.TICK, self.clicked_eeid, self.clicked_point, cursor, self.clicked_delta, self.clicked_distance));
					
		
		

		
