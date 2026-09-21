import canvas;
import editor_gui as gui;
import geometry as geo;
import numpy as np;

from assets import AssetManager;

TYPES = ["text", "line", "rect", "circle"];

GLYPH_WIDTH = 8;
GLYPH_HEIGHT = 8;

DEFAULT_EXTENT = 16;

def get_aabb(decoration):
	x, y = decoration["position"];

	match decoration["type"]:
		case "text":
			shape = decoration["text"];
			lines = shape["text"].split("\n");
			w = max(len(line) for line in lines) * GLYPH_WIDTH * shape["scale"];
			h = (GLYPH_HEIGHT + (len(lines)-1) * (GLYPH_HEIGHT + canvas.GLYPH_LEADING)) * shape["scale"];
			return [x, y, x+w, y+h];

		case "line":
			dx, dy = decoration["line"]["delta"];
			return [min(x, x+dx), min(y, y+dy), max(x, x+dx), max(y, y+dy)];

		case "rect":
			w, h = decoration["rect"]["size"];
			return [min(x, x+w), min(y, y+h), max(x, x+w), max(y, y+h)];

		case "circle":
			r = decoration["circle"]["radius"];
			return [x-r, y-r, x+r, y+r];

	return [x, y, x, y];

def get_body_key(decoration):
	"""Where this sits in the draw order. Sorting and picking share it so they
	can't drift apart."""
	return (decoration["layer"], get_sublayer(decoration), get_depth(decoration));

def get_sublayer(decoration):
	# text draws over anything sharing its layer
	return 1 if decoration["type"] == "text" else 0;

def get_depth(decoration):
	# sorted from the bottom edge, the way entities are
	return get_aabb(decoration)[3];

def get_segment(decoration):
	x, y = decoration["position"];
	dx, dy = decoration["line"]["delta"];
	return [[x, y], [x+dx, y+dy]];

def make_manip(decoration):
	match decoration["type"]:
		case "line":
			return canvas.CanvasManipSegment(get_segment(decoration));

		case "circle":
			return canvas.CanvasManipPoint(decoration["position"], decoration["circle"]["radius"]);

	return canvas.CanvasManipRect(get_aabb(decoration));

def get_colour_palette():
	"""The colour field names its palette in the scene schema. Type.search only
	walks objects, so the list of decorations is stepped over by hand."""
	tree = AssetManager.get_tree("scene");
	decorations = tree.search("decorations") if tree != None else None;
	colour = decorations.inmost.search("colour") if decorations != None else None;
	return getattr(colour, "palette", None);

def gui_draw(decoration):
	decoration["type"] = gui.input_enum("Type", decoration["type"], TYPES);
	decoration["position"] = gui.input_vec2("Position", decoration["position"]);
	decoration["colour"] = list(gui.input_colour("Colour", decoration["colour"], get_colour_palette()));
	decoration["layer"] = gui.input_int("Layer", decoration["layer"], low_bound=-128, high_bound=127);

	match decoration["type"]:
		case "text":
			shape = decoration["text"];
			shape["text"] = gui.input_string("Text", shape["text"]);
			shape["scale"] = gui.input_int("Scale", shape["scale"], low_bound=1);

		case "line":
			decoration["line"]["delta"] = gui.input_vec2("Delta", decoration["line"]["delta"]);

		case "rect":
			shape = decoration["rect"];
			shape["size"] = gui.input_vec2("Size", shape["size"]);
			shape["fill"] = gui.input_bool("Fill", shape["fill"]);

		case "circle":
			shape = decoration["circle"];
			shape["radius"] = gui.input_int("Radius", shape["radius"], low_bound=1);
			shape["fill"] = gui.input_bool("Fill", shape["fill"]);

def canvas_draw(target: canvas.Canvas, decoration, outline=None):
	x, y = decoration["position"];
	colour = tuple(decoration["colour"]);

	match decoration["type"]:
		case "text":
			shape = decoration["text"];
			target.draw_text(decoration["position"], shape["text"], shape["scale"], colour);

		case "line":
			[x0, y0], [x1, y1] = get_segment(decoration);
			target.draw_line(x0, y0, x1, y1, colour);

		case "rect":
			target.draw_aabb(get_aabb(decoration), colour, decoration["rect"]["fill"]);

		case "circle":
			target.draw_circle(x, y, decoration["circle"]["radius"], colour);

	if outline != None:
		target.draw_aabb(get_aabb(decoration), outline);

def canvas_place(point, type, grid: canvas.CanvasGrid=None):
	x, y = grid.snap_point(point) if grid else point;
	decoration = {
		"type": type,
		"position": [int(x), int(y)],
		"colour": [255, 255, 255],
		"layer": 0
	};

	match type:
		case "text":
			decoration["text"] = {"text": "Hello, world!", "scale": 1};

		case "line":
			decoration["line"] = {"delta": [DEFAULT_EXTENT, 0]};

		case "rect":
			decoration["rect"] = {"size": [DEFAULT_EXTENT, DEFAULT_EXTENT], "fill": False};

		case "circle":
			decoration["circle"] = {"radius": DEFAULT_EXTENT//2, "fill": False};

		case _:
			return None;

	return decoration;

def relocate(decoration, point):
	x, y = point;
	decoration["position"][0] = int(x);
	decoration["position"][1] = int(y);

def canvas_drag(decoration, drag: canvas.CanvasManipDrag, grid: canvas.CanvasGrid=None):
	match drag.signal:
		case canvas.CanvasManipDrag.Signal.TICK:
			if drag.inside or decoration["type"] == "text":
				point = np.array(drag.point) + np.array(drag.delta);
				point = grid.snap_point(point) if grid else point;
				relocate(decoration, point);
				return;

			point = grid.snap_point(drag.point) if grid else drag.point;

			match decoration["type"]:
				case "line":
					segment = get_segment(decoration);
					end = geo.segment_closest_end(drag.geometry, drag.start);
					[x0, y0], [x1, y1] = geo.shape_segment(segment, end, point);
					relocate(decoration, (x0, y0));
					decoration["line"]["delta"] = [int(x1-x0), int(y1-y0)];

				case "rect":
					edge = geo.aabb_closest_edge(drag.geometry, drag.start);
					x0, y0, x1, y1 = geo.shape_aabb(get_aabb(decoration), edge, point);
					relocate(decoration, (x0, y0));
					decoration["rect"]["size"] = [int(x1-x0), int(y1-y0)];

				case "circle":
					radius = geo.point_point_dist(decoration["position"], point);
					decoration["circle"]["radius"] = max(1, int(radius));
