import canvas;
import editor_gui as gui;
import math;

NODE_RADIUS = 8;
SEGMENT_RADIUS = 4;

def make(point, grid: canvas.CanvasGrid=None):
	x, y = grid.snap_point(point) if grid else point;
	return {
		"name": "",
		"nodes": [{"position": [x, y], "wait_frames": 0}],
		"loop": True
	};

def get_aabb(navlist):
	x0, y0, x1, y1 = math.inf, math.inf, -math.inf, -math.inf;
	for node in navlist["nodes"]:
		x, y = node["position"];
		x0, y0 = min(x0, x), min(y0, y);
		x1, y1 = max(x1, x), max(y1, y);
	return [x0, y0, x1, y1];

def translate(navlist, delta):
	dx, dy = delta;
	for node in navlist["nodes"]:
		node["position"][0] += dx;
		node["position"][1] += dy;

def relocate(navlist, point):
	x0, y0, _, _ = get_aabb(navlist);
	translate(navlist, (point[0]-x0, point[1]-y0));

def get_segments(navlist):
	"""(from_idx, segment) for each edge from_idx -> from_idx+1, wrapping to close
	the loop if the navlist loops."""
	nodes = navlist["nodes"];
	count = len(nodes);
	segments = [];
	for i in range(count):
		if i == count-1 and not navlist["loop"]:
			break;
		a = nodes[i]["position"];
		b = nodes[(i+1) % count]["position"];
		segments.append((i, [a, b]));
	return segments;

def insert_node_after(navlist, idx, position=None):
	nodes = navlist["nodes"];
	if position == None:
		position = list(nodes[idx]["position"]);
		if idx+1 < len(nodes):
			next_position = nodes[idx+1]["position"];
			position[0] = (position[0] + next_position[0]) // 2;
			position[1] = (position[1] + next_position[1]) // 2;
	else:
		position = [int(position[0]), int(position[1])];
	nodes.insert(idx+1, {"position": position, "wait_frames": 0});
	return idx+1;

def gui_draw(navlist):
	navlist["name"] = gui.input_string("Name", navlist["name"]);
	navlist["loop"] = gui.input_bool("Loop", navlist["loop"]);

def gui_draw_node(node):
	node["position"] = gui.input_vec2("Position", node["position"]);
	node["wait_frames"] = gui.input_int("Wait frames", node["wait_frames"], low_bound=0);

def canvas_draw(target: canvas.Canvas, navlist, colour, selected_node=None, highlight=None):
	nodes = navlist["nodes"];
	count = len(nodes);

	for i in range(count):
		x, y = nodes[i]["position"];
		target.draw_circle(x, y, NODE_RADIUS, colour);
		target.draw_text((x+NODE_RADIUS+2, y-4), str(i), 1, colour);

		if i == 0 and highlight != None:
			target.draw_circle(x, y, NODE_RADIUS+4, highlight);
		if i == selected_node:
			target.draw_circle(x, y, NODE_RADIUS+4, (255, 255, 255));

		if i == count-1 and not navlist["loop"]:
			break;
		bx, by = nodes[(i+1) % count]["position"];
		target.draw_line(x, y, bx, by, colour);
