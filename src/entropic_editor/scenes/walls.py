import canvas;
import editor_gui as gui;
import geometry as geo;
import numpy as np;

def gui_draw(wall):
	wall["type"] = gui.input_enum("Type", wall["type"], ["aabb", "segment"]);

	match wall["type"]:
		case "aabb":
			wall["aabb"] = gui.input_aabb("AABB", wall["aabb"]);
		
		case "segment":
			wall["segment"][0] = gui.input_vec2("A", wall["segment"][0]);
			wall["segment"][1] = gui.input_vec2("B", wall["segment"][1]);

def canvas_draw(canvas: canvas.Canvas, wall, colour):
	match wall["type"]:
		case "aabb":
			canvas.draw_aabb(wall["aabb"], colour, False);
	
		case "segment":
			(x0, y0), (x1, y1) = wall["segment"];
			canvas.draw_line(x0, y0, x1, y1, colour);		
			canvas.draw_circle(x0, y0, 2, colour);
			canvas.draw_circle(x1, y1, 2, colour);

def canvas_place(point, type, grid: canvas.CanvasGrid=None):
	x, y = point;
	x0, y0 = grid.snap_point(point) if grid else point;
	x1, y1 = x0+16, y0+16;
	wall = {
		"type": type
	};

	match type:
		case "aabb":
			wall["aabb"] = [x0, y0, x1, y1];

		case "segment":
			deltas = [abs(x-x0), abs(y-y0), abs(x-x1), abs(y-y1)];
			min_idx = min(range(len(deltas)), key=deltas.__getitem__);
			segment = None;
			if min_idx == 0:				
				segment = [[x0, y0], [x0, y1]];
			elif min_idx == 1:			
				segment = [[x0, y0], [x1, y0]];
			elif min_idx == 2:			
				segment = [[x1, y0], [x1, y1]];
			elif min_idx == 3:	
				segment = [[x0, y1], [x1, y1]];
			wall["segment"] = segment;

		case _:
			return None;

	return wall;

def canvas_drag(wall, drag: canvas.CanvasManipDrag, grid: canvas.CanvasGrid=None):
	match drag.signal:
		case canvas.CanvasManipDrag.Signal.TICK:
			match wall["type"]:
				case "aabb":
					if drag.inside:
						point = np.array(drag.point) + np.array(drag.delta);
						point = grid.snap_point(point) if grid else point;
						wall["aabb"] = geo.relocate_aabb(wall["aabb"], point);
					else:
						point = grid.snap_point(drag.point) if grid else drag.point;
						edge = geo.aabb_closest_edge(drag.geometry, drag.start);
						wall["aabb"] = geo.shape_aabb(wall["aabb"], edge, point);
				
				case "segment":
					if drag.inside:
						point = np.array(drag.point) + np.array(drag.delta);
						point = grid.snap_point(point) if grid else point;
						wall["segment"] = geo.relocate_segment(wall["segment"], point);
					else:
						point = grid.snap_point(drag.point) if grid else drag.point;
						end = geo.segment_closest_end(drag.geometry, drag.start);
						wall["segment"] = geo.shape_segment(wall["segment"], end, point);