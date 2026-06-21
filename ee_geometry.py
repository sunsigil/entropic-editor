import numpy as np;
import math;
import enum;
import copy;

class Orientation(enum.Enum):
	EAST = 0
	NORTH = 1
	WEST = 2
	SOUTH = 3

def is_left(a, b, c):
	a = np.array(a);
	b = np.array(b);
	c = np.array(c);
	ab = b-a;
	ac = c-a;
	np.cross(ab, ac);

def point_point_dist(a, b):
	a = np.array(a);
	b = np.array(b);
	return np.linalg.norm(b-a);

def aabb_contains_point(aabb, point):
	x0, y0, x1, y1 = aabb;
	x, y = point;
	if x < x0 or x > x1:
		return False;
	if y < y0 or y > y1:
		return False;
	return True;

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

def aabb_point_dist(aabb, point):
	sq_dist = 0;
	for i in range(2):
		v = point[i];
		if v < aabb[i]:
			sq_dist += (aabb[i] - v) * (aabb[i] - v);
		if v > aabb[2+i]:
			sq_dist += (v - aabb[2+i]) * (v - aabb[2+i]);
	return math.sqrt(sq_dist);

def aabb_point_sdf(aabb, point):
	x0, y0, x1, y1 = aabb;
	x, y = point;
	dx = max([x0 - x, x - x1]);
	dy = max([y0 - y, y - y1]);
	out_dx = max(dx, 0);
	out_dy = max(dy, 0);
	out_d = np.linalg.norm(np.array((out_dx, out_dy)));
	in_d = min(max([dx, dy]), 0);
	return out_d + in_d;

def aabb_closest_edge(aabb, point):
	x0, y0, x1, y1 = aabb;
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

def shape_aabb(aabb, edge, point):
	aabb = copy.copy(aabb);

	x0, y0, x1, y1 = aabb;
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
		aabb = x0, y0, x1, y1;
	
	return aabb;

def relocate_aabb(aabb, point):
	aabb = copy.copy(aabb);

	x0, y0, x1, y1 = aabb;
	w, h = x1-x0, y1-y0;
	x, y = point;

	return x, y, x+w, y+h;

def shape_segment(segment, end, point):
	segment = copy.copy(segment);

	a, b = segment;
	x0, y0 = a;
	x1, y1 = b;

	match end:
		case 0:
			x0, y0 = point;
		case 1:
			x1, y1 = point;
	if x0 != x1 or y0 != y1:
		a = x0, y0;
		b = x1, y1;
		segment = a, b;
	
	return segment;

def relocate_segment(segment, point):
	segment = copy.copy(segment);

	(x0, y0), (x1, y1) = segment;
	dx, dy = x1-x0, y1-y0;
	x, y = point;

	a = x, y;
	b = x+dx, y+dy;
	return a, b;

def segment_closest_end(segment, point):
	a, b = segment;
	a = np.array(segment[0]);
	b = np.array(segment[1]);
	p = np.array(point);
	da = np.linalg.norm(p-a);
	db = np.linalg.norm(p-b);
	if db < da:
		return 1;
	return 0;

def segment_point_sdf(segment, point):
	a = np.array(segment[0]);
	b = np.array(segment[1]);
	p = np.array(point);
	h = min(1, max(0, np.dot(p-a, b-a)/ np.dot(b-a, b-a)));
	return np.linalg.norm(p-a-(b-a)*h);