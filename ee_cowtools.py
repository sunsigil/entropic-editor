import OpenGL;
OpenGL.FULL_LOGGING = True;
from OpenGL.GL import *;
from imgui_bundle import imgui;
import math;
from enum import Enum;

class Orientation(Enum):
	EAST = 0
	NORTH = 1
	WEST = 2
	SOUTH = 3

def foldl(f, acc, xs):
	if len(xs) == 0:
		return acc;
	else:
		h, t = xs[0], xs[1:];
		return foldl(f, f(acc, h), t);

def foldr(f, acc, xs):
	if len(xs) == 0:
		return acc;
	else:
		h, t = xs[0], xs[1:];
		return f(h, foldr(f, acc, t));

def make_texture(buffer, width, height):
	texture = glGenTextures(1);
	glBindTexture(GL_TEXTURE_2D, texture);
	glTexParameteri(GL_TEXTURE_2D, 	GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, 	GL_TEXTURE_MAG_FILTER, GL_NEAREST);
	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, buffer);
	return texture;

def aabb_contains_point(aabb, point):
	x0, y0, x1, y1 = aabb;
	x, y = point;
	if x < x0 or x > x1:
		return False;
	if y < y0 or y > y1:
		return False;
	return True;

def move_aabb(aabb, delta):
	x0, y0, x1, y1 = aabb;
	dx, dy = delta;
	return x0+dx, y0+dy, x1+dx, y1+dy;

def enforce_key(dict, key, default_value):
	if not key in dict:
		dict[key] = default_value;

def clamp(v, a, b):
	return min(max(v, a), b);

def aabb_contains_aabb(aabb_0, aabb_1):
	x0, y0, x1, y1 = aabb_1;
	a = x0, y0;
	b = x1, y0;
	c = x1, y1;
	d = x0, y1;
	return (
		aabb_contains_point(aabb_0, a) and
		aabb_contains_point(aabb_0, b) and
		aabb_contains_point(aabb_0, c) and
		aabb_contains_point(aabb_0, d)
	);

def aabb_equals(a, b):
	for i in range(4):
		if a[i] != b[i]:
			return False;
	return True;

class EEID:
	def __iter__(self):
		self.eeid = 0;
		return self;

	def __next__(self):
		result = self.eeid;
		self.eeid += 1;
		return result;

def aabb_point_dist(aabb, point):
	sq_dist = 0;
	for i in range(2):
		v = point[i];
		if v < aabb[i]:
			sq_dist += (aabb[i] - v) * (aabb[i] - v);
		if v > aabb[2+i]:
			sq_dist += (v - aabb[2+i]) * (v - aabb[2+i]);
	return math.sqrt(sq_dist);

def cross2d(a, b):
	return a[0]*b[1] - a[1]*b[0];

def mag2d(v):
	x, y = v;
	return math.sqrt(x*x+y*y);

def is_left(a, b, c):
	ab = (b[0]-a[0], b[1]-a[1]);
	ac = (c[0]-a[0], c[1]-a[1]);
	return cross2d(ab, ac) > 0;

def aabb_closest_edge(aabb, point):
	x0, y0, x1, y1 = aabb;
	x, y = point;
	ne = is_left((x0, y0), (x1, y1), point);
	nw = is_left((x0, y1), (x1, y0), point);
	if ne and not nw:
		return Orientation.WEST;
	if ne and nw:
		return Orientation.SOUTH;
	if not ne and nw:
		return Orientation.EAST;
	return Orientation.NORTH;

def aabb_closest_point(aabb, point):
	if not aabb_contains_point(aabb, point):
		q = [0, 0];
		for i in range(2):
			v = point[i];
			if v < aabb[i]:
				v = aabb[i];
			if v > aabb[2+i]:
				v = aabb[2+i];
			q[i] = v;
		return q;
	else:
		edge = aabb_closest_edge(aabb, point);
		match edge:
			case Orientation.EAST:
				return (aabb[2], point[1]);
			case Orientation.NORTH:
				return (point[0], aabb[1]);
			case Orientation.WEST:
				return (aabb[0], point[1]);
			case Orientation.SOUTH:
				return (point[0], aabb[3]);
		return None;

def point_point_dist(a, b):
	ax, ay = a;
	bx, by = b;
	dx = bx - ax;
	dy = by - ay;
	return math.sqrt(dx*dx+dy*dy);

def aabb_point_sdf(aabb, point):
	x0, y0, x1, y1 = aabb;
	x, y = point;
	dx = max([x0 - x, x - x1]);
	dy = max([y0 - y, y - y1]);
	out_dx = max(dx, 0);
	out_dy = max(dy, 0);
	out_d = mag2d((out_dx, out_dy));
	in_d = min(max([dx, dy]), 0);
	return out_d + in_d;