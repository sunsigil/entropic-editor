from imgui_bundle import imgui;
import glfw;
import csv;
import copy;

from cowtools import *;
from canvas import *;
from assets import *;
from sprites import SpriteBank;
from input import InputManager;
from editor_gui import *;
from geometry import *;
import scenes.walls;
import scenes.tilemaps;
import scenes.navlists;
import scenes.decorations;
import scripts;

#########################################################
## HELPERS

# a pasted copy lands this far from the original, stepping further out with
# each paste so repeats don't stack on one spot
PASTE_OFFSET = 16;

def index_of(items, item):
	return next((i for i, x in enumerate(items) if x is item), None);

def get_entity_sprite(entity):
	prototype = AssetManager.search("prototype", entity["prototype"]);
	if prototype == None:
		return None;
	return SpriteBank.search(prototype["sprite"], safe=False);

def get_entity_aabb(entity):
	x, y = entity["position"];

	prototype = AssetManager.search("prototype", entity["prototype"]);
	if prototype != None:
		sprite = SpriteBank.search(prototype["sprite"], safe=False);
		if sprite != None:
			dx, dy = prototype["sprite_offset"];
			return [x+dx, y+dy, x+dx+sprite.frame_width, y+dy+sprite.frame_height];
	
		if prototype["has_blocker"]:
			x0, y0, x1, y1 = prototype["blocker"];
			return [x+x0, y+y0, x+x1, y+y1];
		elif prototype["has_trigger"]:
			x0, y0, x1, y1 = prototype["trigger"];
			return [x+x0, y+y0, x+x1, y+y1];

	return [x-8, y-8, x+8, y+8];

def get_entity_body_key(entity):
	"""Where this sits in the draw order. Sorting and picking share it so they
	can't drift apart. Entities all live on layer 0."""
	return (0, 0, get_entity_depth(entity));

def get_entity_depth(entity):
	prototype = AssetManager.search("prototype", entity["prototype"]);
	y_offset = prototype["y_sort_offset"] if prototype != None else 0;
	return get_entity_aabb(entity)[3] + y_offset;

def get_script_data(entity, key):
	for entry in entity["script_data"]:
		for datum in entry["data"]:
			if datum["signature"]["key"] == key:
				return datum;
	return None;

def rectify_entity_script_data(entity):
	prototype = AssetManager.search("prototype", entity["prototype"]);
	if prototype == None:
		return;

	prototype["script_data"] = scripts.rectify_all_script_data(prototype["scripts"], prototype["script_data"]);
	entity["script_data"] = scripts.rectify_all_script_data(prototype["scripts"], entity["script_data"], prototype["script_data"]);
	
#########################################################
## SCENE EDITOR

class EditMode(Enum):
	ENTITIES = 0,
	TILEMAP = 1,
	WALLS = 2,
	DOORS = 3,
	NAVLISTS = 4,
	DECORATIONS = 5,
	PROPERTIES = 6

class TilemapEditor:
	TOOLS = ["paint", "rect", "fill"];

	def __init__(self, parent):
		self.parent = parent;
		self.tilemaps = None;
		self.tilemap = None;

		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(self.parent.canvas_io, self.event_queue);

		self.tool = "paint";
		self.selected_frame = 0;
		self.cursor = None;
		self.rect_anchor = None;
		self.paint_last = None;

	def on_load_scene(self):
		self.tilemaps = self.parent.scene["tilemaps"];
		self.tilemap = self.tilemaps[0] if len(self.tilemaps) > 0 else None;
		self.canvas_manip.clear();
		self.rect_anchor = None;
		self.paint_last = None;

	def validate(self):
		# the scene's list and its contents can be swapped out under us by an undo
		self.tilemaps = self.parent.scene["tilemaps"];
		if index_of(self.tilemaps, self.tilemap) == None:
			self.tilemap = self.tilemaps[0] if len(self.tilemaps) > 0 else None;
			self.rect_anchor = None;
			self.paint_last = None;

	def create_tilemap(self):
		tilemap = AssetManager.get_tree("scene").search("tilemaps").inmost.prototype();
		self.tilemaps.append(tilemap);
		self.tilemap = tilemap;

	def delete_tilemap(self):
		idx = index_of(self.tilemaps, self.tilemap);
		if idx == None:
			return;
		del self.tilemaps[idx];
		self.tilemap = self.tilemaps[min(idx, len(self.tilemaps)-1)] if len(self.tilemaps) > 0 else None;
		self.rect_anchor = None;
		self.paint_last = None;

	def label_tilemap(self, tilemap):
		if tilemap == None:
			return "None";
		idx = index_of(self.tilemaps, tilemap);
		palette = tilemap["palette"] if len(tilemap["palette"]) > 0 else "no palette";
		return f"{idx}: {palette} ({"fg" if tilemap["is_foreground"] else "bg"})";

	def draw_palette(self):
		self.tilemap["palette"] = input_asset("Palette", self.tilemap["palette"], "sprite");

		sprite = SpriteBank.search(self.tilemap["palette"]);
		if sprite == None:
			return;
	
		wdw_w = imgui.get_content_region_avail().x;
		cols = max(int(wdw_w // 72), 1);
		rows = int(math.ceil(sprite.frame_count / cols));

		i = 0;
		for r in range(rows):
			for c in range(cols):
				if i < sprite.frame_count:
					tint = (0.5, 0.5, 0.5, 1) if i == self.selected_frame else (1, 1, 1, 1);
					if imgui.image_button(f"##{i}", imgui.ImTextureRef(sprite.frame_textures[i]), (64, 64), tint_col=tint):
						self.selected_frame = i;
					imgui.same_line();
				i += 1;
			imgui.new_line();
	
	def draw_gui(self):
		self.validate();

		if imgui.button("New"):
			self.create_tilemap();
		if self.tilemap != None:
			imgui.same_line();
			if imgui.button("Delete"):
				self.delete_tilemap();

		self.tilemap = combo("Tilemap", self.tilemap, self.tilemaps, self.label_tilemap);
		if self.tilemap == None:
			return;

		type_last = self.tilemap["type"];
		self.tilemap["type"] = input_enum("Type", self.tilemap["type"], ["sparse", "dense"]);
		if type_last == "sparse" and self.tilemap["type"] == "dense":
			self.tilemap["dense"] = scenes.tilemaps.sparse_to_dense(self.tilemap["sparse"]);
		if type_last == "dense" and self.tilemap["type"] == "sparse":
			self.tilemap["sparse"] = scenes.tilemaps.dense_to_sparse(self.tilemap["dense"]);
		
		if self.tilemap["type"] == "dense":
			dense = self.tilemap["dense"];
			dense["position"] = input_vec2("Position", dense["position"]);
			rows = input_int("Rows", dense["rows"], low_bound=0);
			columns = input_int("Columns", dense["columns"], low_bound=0);
			if rows != dense["rows"] or columns != dense["columns"] or len(dense["frame_indices"]) != rows*columns:
				scenes.tilemaps.resize_dense(dense, rows, columns);
		
		self.tilemap["is_foreground"] = input_bool("Is Foreground", self.tilemap["is_foreground"]);

		self.tool = input_enum("Tool", self.tool, TilemapEditor.TOOLS);
		imgui.text_disabled("shift: erase, alt: pick, right drag: pan");

		self.draw_palette();

		self.tilemap["csv"] = input_file("CSV", self.tilemap["csv"], "*.csv", "assets/scenes/tilemaps", return_absolute=True);
		if imgui.button("Import"):
			scenes.tilemaps.import_tilemap(self.tilemap, self.tilemap["csv"]);
		imgui.same_line();
		if imgui.button("Export"):
			scenes.tilemaps.export_tilemap(self.tilemap, self.tilemap["csv"]);

	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CanvasManipViewDrag):
				CanvasManipulator.default_view_drag_handler(self.parent.canvas, event);
	
	def edit(self):
		if self.cursor == None:
			self.paint_last = None;
			if not InputManager.is_held(glfw.MOUSE_BUTTON_LEFT):
				self.rect_anchor = None;
			return;
	
		palette = SpriteBank.search(self.tilemap["palette"]);
		self.selected_frame = clamp(self.selected_frame, 0, palette.frame_count-1);
		col, row = scenes.tilemaps.world_to_cell(self.tilemap, *self.cursor);

		if InputManager.is_held(glfw.KEY_LEFT_ALT):
			self.paint_last = None;
			if InputManager.is_pressed(glfw.MOUSE_BUTTON_LEFT):
				frame_idx = scenes.tilemaps.get_tile(self.tilemap, col, row);
				if frame_idx != None:
					self.selected_frame = frame_idx;
			return;

		frame_idx = None if InputManager.is_held(glfw.KEY_LEFT_SHIFT) else self.selected_frame;

		paint_last = self.paint_last;
		self.paint_last = None;

		match self.tool:
			case "paint":
				if InputManager.is_held(glfw.MOUSE_BUTTON_LEFT):
					start = paint_last if paint_last != None else (col, row);
					scenes.tilemaps.stroke(self.tilemap, *start, col, row, frame_idx);
					self.paint_last = (col, row);

			case "rect":
				if InputManager.is_pressed(glfw.MOUSE_BUTTON_LEFT):
					self.rect_anchor = (col, row);
				if InputManager.is_released(glfw.MOUSE_BUTTON_LEFT) and self.rect_anchor != None:
					scenes.tilemaps.fill_rect(self.tilemap, *self.rect_anchor, col, row, frame_idx);
					self.rect_anchor = None;

			case "fill":
				if InputManager.is_pressed(glfw.MOUSE_BUTTON_LEFT):
					scenes.tilemaps.flood_fill(self.tilemap, col, row, frame_idx);

	def draw_canvas(self):
		if self.tilemap == None or self.cursor == None:
			return;

		colour = (255, 255, 255);
		if InputManager.is_held(glfw.KEY_LEFT_ALT):
			colour = (128, 255, 128);
		elif InputManager.is_held(glfw.KEY_LEFT_SHIFT):
			colour = (255, 128, 128);

		col, row = scenes.tilemaps.world_to_cell(self.tilemap, *self.cursor);
		if self.rect_anchor != None:
			aabb = scenes.tilemaps.get_cell_aabb(self.tilemap, *self.rect_anchor, col, row);
		else:
			aabb = scenes.tilemaps.get_cell_aabb(self.tilemap, col, row);
		self.parent.canvas.draw_aabb(aabb, colour);

	def tick(self):
		self.validate();

		self.canvas_manip.tick();
		self.handle_events();

		if self.tilemap == None:
			self.cursor = None;
			return;

		if self.parent.canvas_io.is_cursor_in_bounds():
			self.cursor = self.parent.canvas_io.get_cursor();
		else:
			self.cursor = None;
		
		self.edit();

class WallEditor:
	def __init__(self, parent):
		self.parent = parent;
		self.walls = None;

		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(self.parent.canvas_io, self.event_queue);
		self.manip_registry = CanvasManipRegistry();
		self.selection_context = SelectionContext();
		self.trash = Trash(deferred=True);

		self.place_mode = "none";

	def on_load_scene(self):
		self.walls = self.parent.scene["walls"];
		self.canvas_manip.clear();
		self.manip_registry.clear();
		self.selection_context.clear();
		self.trash.clear();
	
	def draw_gui(self):
		if self.walls == None:
			return;

		self.place_mode = input_enum("Place mode", self.place_mode, ["none", "aabb", "segment"]);

		for idx, wall in enumerate(self.walls):
			imgui.set_next_item_open(self.selection_context.is_selected(wall));
			node_open = imgui.tree_node(f"Wall {idx}##{id(self.walls)}{idx}");

			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("Delete"):
					self.trash.trash_index(self.walls, idx);
					imgui.close_current_popup();
				imgui.end_popup();
			self.trash.flush();

			if node_open:
				scenes.walls.gui_draw(wall);
				imgui.tree_pop();

	def synchronize_manip(self):
		def make_shape(wall):
			match wall["type"]:
				case "aabb":
					return CanvasManipRect(wall["aabb"]);
				case "segment":
					return CanvasManipSegment(wall["segment"]);
		shapes = [make_shape(x) for x in self.walls];
		
		self.manip_registry.update(self.walls, shapes);
		self.canvas_manip.synchronize(self.manip_registry);
	
	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CanvasManipClick):
				hit = event.eeid != None;
				if hit:
					self.selection_context.select(self.manip_registry.search(event.eeid), exclusive=True);
					continue;
				if InputManager.is_held(glfw.KEY_LEFT_SHIFT):
					continue;
				
				new_wall = scenes.walls.canvas_place(event.point, self.place_mode, self.parent.canvas_grid);
				if new_wall != None:
					self.walls.append(new_wall);
					self.selection_context.select(new_wall);

			if isinstance(event, CanvasManipDrag):
				if event.eeid != None:
					wall = self.manip_registry.search(event.eeid);
					scenes.walls.canvas_drag(wall, event, self.parent.canvas_grid);
	
	def tick(self):
		if self.walls == None:
			return;
	
		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_D):
			selected = self.selection_context.get_selection(True);
			self.trash.trash_item(self.walls, selected);
			self.trash.flush();
			self.selection_context.clear();
		
		self.synchronize_manip();
		self.canvas_manip.tick();
		self.handle_events();

class DecorationEditor:
	def __init__(self, parent):
		self.parent = parent;
		self.decorations = None;

		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(self.parent.canvas_io, self.event_queue);
		self.manip_registry = CanvasManipRegistry();
		self.selection_context = SelectionContext();
		self.clipboard = Clipboard();
		self.trash = Trash(deferred=True);

		self.place_mode = "none";

	def on_load_scene(self):
		self.decorations = self.parent.scene["decorations"];
		self.canvas_manip.clear();
		self.manip_registry.clear();
		self.selection_context.clear();
		self.trash.clear();

	def draw_gui(self):
		if self.decorations == None:
			return;

		self.place_mode = input_enum("Place mode", self.place_mode, ["none"] + scenes.decorations.TYPES);

		for idx, decoration in enumerate(self.decorations):
			imgui.set_next_item_open(self.selection_context.is_selected(decoration));
			node_open = imgui.tree_node(f"Decoration {idx}##{id(self.decorations)}{idx}");

			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("Delete"):
					self.trash.trash_index(self.decorations, idx);
					imgui.close_current_popup();
				imgui.end_popup();
			self.trash.flush();

			if node_open:
				scenes.decorations.gui_draw(decoration);
				imgui.tree_pop();

	def synchronize_manip(self):
		shapes = [scenes.decorations.make_manip(x) for x in self.decorations];
		keys = [scenes.decorations.get_body_key(x) for x in self.decorations];

		self.manip_registry.update(self.decorations, shapes, keys);
		self.canvas_manip.synchronize(self.manip_registry);

	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CanvasManipClick):
				hit = event.eeid != None;
				if hit:
					self.selection_context.select(self.manip_registry.search(event.eeid), exclusive=True);
					continue;
				if InputManager.is_held(glfw.KEY_LEFT_SHIFT):
					continue;

				new_decoration = scenes.decorations.canvas_place(event.point, self.place_mode, self.parent.canvas_grid);
				if new_decoration != None:
					self.decorations.append(new_decoration);
					self.selection_context.select(new_decoration);

			if isinstance(event, CanvasManipDrag):
				if event.eeid != None:
					decoration = self.manip_registry.search(event.eeid);
					scenes.decorations.canvas_drag(decoration, event, self.parent.canvas_grid);

	def tick(self):
		if self.decorations == None:
			return;

		if InputManager.is_command(glfw.KEY_C):
			self.clipboard.copy(self.selection_context.get_selection(single=True), copy_mode=Clipboard.CopyMode.DEEP, exclusive=True);
		if InputManager.is_command(glfw.KEY_V):
			pasted = self.clipboard.paste(self.decorations);
			offset = PASTE_OFFSET * self.clipboard.paste_count;
			if len(pasted) > 0:
				self.selection_context.clear();
			for decoration in pasted:
				x, y = decoration["position"];
				scenes.decorations.relocate(decoration, self.parent.canvas_grid.snap_point((x+offset, y+offset)));
				self.selection_context.select(decoration);

		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_D):
			selected = self.selection_context.get_selection(True);
			self.trash.trash_item(self.decorations, selected);
			self.trash.flush();
			self.selection_context.clear();

		self.synchronize_manip();
		self.canvas_manip.tick();
		self.handle_events();

class DoorEditor:
	class Door:
		def __init__(self, scene, entity):
			self.scene = scene;
			self.entity = entity;
			self.pointers = [];
		
		def update(self, doors):
			for door in doors:
				if door is self:
					continue;
				to_scene = get_script_data(door.entity, "to_scene");
				if to_scene == None or to_scene["value"] != self.scene["name"]:
					continue;
				to_entity = get_script_data(door.entity, "to_entity");
				if to_entity == None or to_entity["value"] != self.entity["name"]:
					continue;
				self.pointers.append(door);
	
		def points_to(self):
			to_scene = get_script_data(self.entity, "to_scene");
			to_entity = get_script_data(self.entity, "to_entity");
			return to_scene["value"] != "" and to_entity["value"] != "";

		def is_pointed_to(self):
			return len(self.pointers) > 0;

	class Selector:
		def __init__(self, parent, door):
			self.parent = parent;
			self.door = door;
			self.open = True;

		def draw(self):
			_, self.open = imgui.begin("Select door", self.open);
			for scene in self.parent.door_hierarchy:
				if imgui.tree_node(f"{scene}##{id(scene)}"):
					for door in self.parent.door_hierarchy[scene]:
						if door == self.door:
							continue;
						to_scene = get_script_data(self.door.entity, "to_scene");
						to_entity = get_script_data(self.door.entity, "to_entity");
						was_selected = door.entity["name"] == to_entity["value"];
						clicked, value = imgui.menu_item(f"{door.entity["name"]}##{id(door.entity)}", "", was_selected);
						if clicked:
							if was_selected:
								to_scene["value"] = "";
								to_entity["value"] = "";
							else:
								to_scene["value"] = door.scene["name"];
								to_entity["value"] = door.entity["name"];
					imgui.tree_pop();
			imgui.end();
	
	def __init__(self, parent):
		self.parent = parent;
		self.door_pool = [];
		self.door_hierarchy = {};

		self.selector = None;
	
	def poll_all_doors(self):
		self.door_pool = [];
		self.door_hierarchy = {};
		for scene in AssetManager.get_all("scene"):
			self.door_hierarchy[scene["name"]] = [];
			for entity in scene["entities"]:
				prototype = AssetManager.search("prototype", entity["prototype"]);
				if prototype == None:
					continue;
				if "door" in prototype["scripts"]:
					door = DoorEditor.Door(scene, entity);
					self.door_pool.append(door);
					self.door_hierarchy[scene["name"]].append(door);
	
	def logic(self):
		self.poll_all_doors();
		for door in self.door_pool:
			door.update(self.door_pool);
	
	def gui(self):
		for scene in self.door_hierarchy:
			if scene == self.parent.scene["name"]:
				for door in self.door_hierarchy[scene]:
					if imgui.tree_node(door.entity["name"]+"##"+str(id(door.entity))):
						to_scene = get_script_data(door.entity, "to_scene");
						to_entity = get_script_data(door.entity, "to_entity");
						if AssetManager.search("scene", to_scene["value"]) == None:
							to_scene["value"] = "";
						elif next((x for x in AssetManager.search("scene", to_scene["value"])["entities"] if x["name"] == to_entity["value"]), None) == None:
							to_entity["value"] = "";
						
						if to_scene["value"] == "":
							imgui.text("Unlinked");
						elif to_entity["value"] == "":
							imgui.text(f"Linked to scene {to_scene["value"]}");
						else:
							imgui.text(f"Linked to {to_scene["value"]}.{to_entity["value"]}");
						
						imgui.same_line();
						if imgui.button("Browse"):
							self.selector = DoorEditor.Selector(self, door);
						
						orientation = get_script_data(door.entity, "orientation");
						orientation["value"] = input_orientation("Orientation", orientation["value"]);
						
						imgui.tree_pop();		

		if self.selector != None:
			self.selector.draw();
			if not self.selector.open:
				self.selector = None;

	def draw(self):
		for scene in self.door_hierarchy:
			if scene == self.parent.scene["name"]:
				for door in self.door_hierarchy[scene]:
					door_gizmo = SpriteBank.search("editor_door");
					x, y = door.entity["position"];

					prototype = AssetManager.search("prototype", door.entity["prototype"]);
					if prototype["has_trigger"]:
						x0, y0, x1, y1 = prototype["trigger"];
						w, h = x1-x0, y1-y0;
						x = x + x0 + w/2;
						y = y + y1;
					
					idx = 0;
					if door.points_to() and not door.is_pointed_to():
						idx = 1;
					if door.is_pointed_to() and not door.points_to():
						idx = 2;
					if door.points_to() and door.is_pointed_to():
						idx = 3;
					self.parent.canvas.draw_image(x-door_gizmo.frame_width/2, y-door_gizmo.frame_height, door_gizmo.frame_images[idx]);

					arrow_gizmo = SpriteBank.search("editor_arrow");
					orientation = get_script_data(door.entity, "orientation");
					x_off = -arrow_gizmo.frame_width/2;
					y_off = -door_gizmo.frame_height/2-arrow_gizmo.frame_height/2;
					match orientation["value"]:
						case 1:
							x_off += door_gizmo.frame_width/2+arrow_gizmo.frame_width/2;
						case 2:
							y_off -= door_gizmo.frame_height/2+arrow_gizmo.frame_height/2;
						case 3:
							x_off -= door_gizmo.frame_width/2+arrow_gizmo.frame_width/2;
						case 4:
							y_off += door_gizmo.frame_height/2+arrow_gizmo.frame_height/2;
					self.parent.canvas.draw_image(x+x_off, y+y_off, arrow_gizmo.frame_images[orientation["value"]], c=(255, 128, 0));

class NavlistEditor:
	# node_idx == None means the whole navlist is selected (as a body), rather
	# than any one node in it.
	class ManipIndex:
		def __init__(self, navlist, node_idx):
			self.navlist = navlist;
			self.node_idx = node_idx;
		def __eq__(self, value):
			if not isinstance(value, NavlistEditor.ManipIndex):
				return False;
			return self.navlist is value.navlist and self.node_idx == value.node_idx;

	# a click target for the connecting line from_idx -> from_idx+1; hitting one
	# inserts a node there rather than selecting anything
	class SegmentRef:
		def __init__(self, navlist, from_idx):
			self.navlist = navlist;
			self.from_idx = from_idx;
		def __eq__(self, value):
			if not isinstance(value, NavlistEditor.SegmentRef):
				return False;
			return self.navlist is value.navlist and self.from_idx == value.from_idx;

	def __init__(self, parent):
		self.parent = parent;
		self.navlists = None;

		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(parent.canvas_io, self.event_queue);
		self.manip_registry = CanvasManipRegistry();
		self.selection_context = SelectionContext();
		self.clipboard = Clipboard();
		self.clipboard_kind = None;
		self.trash = Trash(deferred=True);

		self.place_mode = False;

	def on_load_scene(self):
		self.navlists = self.parent.scene["navlists"];
		self.canvas_manip.clear();
		self.manip_registry.clear();
		self.selection_context.clear();
		self.trash.clear();

	# Entities address navlists by position in this list, so a deletion has to
	# repoint everything above it.
	def _delete_navlist(self, idx):
		for entity in self.parent.scene["entities"]:
			datum = get_script_data(entity, "navlist_idx");
			if datum == None:
				continue;
			if datum["value"] == idx:
				datum["value"] = -1;
			elif datum["value"] > idx:
				datum["value"] -= 1;
		self.trash.trash_index(self.navlists, idx);

	# One pass over the whole scene registers a body (whole-list move), a
	# segment per connecting line (click-to-insert), and a point per node
	# (move that node) -- all at once, so there's no mode to switch between.
	# Keys break ties when they overlap: a node sitting on a segment wins the
	# segment, and either wins the body.
	def synchronize_manip(self):
		objects = [];
		shapes = [];
		keys = [];

		for navlist in self.navlists:
			nodes = navlist["nodes"];
			if len(nodes) == 0:
				continue;

			objects.append(NavlistEditor.ManipIndex(navlist, None));
			shapes.append(CanvasManipRect(scenes.navlists.get_aabb(navlist)));
			keys.append(0);

			for from_idx, segment in scenes.navlists.get_segments(navlist):
				objects.append(NavlistEditor.SegmentRef(navlist, from_idx));
				shapes.append(CanvasManipSegment(segment, radius=scenes.navlists.SEGMENT_RADIUS));
				keys.append(1);

			for idx, node in enumerate(nodes):
				objects.append(NavlistEditor.ManipIndex(navlist, idx));
				shapes.append(CanvasManipPoint(node["position"], scenes.navlists.NODE_RADIUS));
				keys.append(2);

		self.manip_registry.update(objects, shapes, keys);
		self.canvas_manip.synchronize(self.manip_registry);

	def handle_events(self):
		grid = self.parent.canvas_grid if self.parent.snap else None;

		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CanvasManipClick):
				target = self.manip_registry.search(event.eeid) if event.eeid != None else None;

				if isinstance(target, NavlistEditor.SegmentRef):
					point = grid.snap_point(event.point) if grid else event.point;
					inserted = scenes.navlists.insert_node_after(target.navlist, target.from_idx, position=point);
					self.selection_context.select(NavlistEditor.ManipIndex(target.navlist, inserted), exclusive=True);
					continue;

				if target != None:
					self.selection_context.select(target, exclusive=True);
					continue;
				if not self.place_mode:
					self.selection_context.clear();
					continue;
				navlist = scenes.navlists.make(event.point, grid);
				self.navlists.append(navlist);
				self.selection_context.select(NavlistEditor.ManipIndex(navlist, 0), exclusive=True);

			if isinstance(event, CanvasManipDrag):
				if event.eeid == None or event.signal != CanvasManipDrag.Signal.TICK:
					continue;
				target = self.manip_registry.search(event.eeid);
				if not isinstance(target, NavlistEditor.ManipIndex):
					continue;
				point = np.array(event.point) + np.array(event.delta);
				point = grid.snap_point(point) if grid else point;
				if target.node_idx == None:
					scenes.navlists.relocate(target.navlist, point);
				else:
					target.navlist["nodes"][target.node_idx]["position"] = list(point);

	def logic(self):
		if self.navlists == None:
			return;

		if InputManager.is_command(glfw.KEY_D):
			selection = self.selection_context.get_selection(single=True);
			if selection != None:
				if selection.node_idx != None:
					nodes = selection.navlist["nodes"];
					if len(nodes) > 1:
						self.trash.trash_index(nodes, selection.node_idx);
						self.selection_context.clear();
				elif selection.navlist in self.navlists:
					self._delete_navlist(self.navlists.index(selection.navlist));
					self.selection_context.clear();
			self.trash.flush();

		if InputManager.is_command(glfw.KEY_C):
			selection = self.selection_context.get_selection(single=True);
			if selection != None:
				if selection.node_idx != None:
					node = selection.navlist["nodes"][selection.node_idx];
					self.clipboard.copy(node, copy_mode=Clipboard.CopyMode.DEEP, exclusive=True);
					self.clipboard_kind = "node";
				else:
					self.clipboard.copy(selection.navlist, copy_mode=Clipboard.CopyMode.DEEP, exclusive=True);
					self.clipboard_kind = "navlist";

		if InputManager.is_command(glfw.KEY_V):
			if self.clipboard_kind == "navlist":
				pasted = self.clipboard.paste(self.navlists);
				offset = PASTE_OFFSET * self.clipboard.paste_count;
				if len(pasted) > 0:
					self.selection_context.clear();
				for navlist in pasted:
					scenes.navlists.translate(navlist, (offset, offset));
					self.selection_context.select(NavlistEditor.ManipIndex(navlist, None), exclusive=True);
			elif self.clipboard_kind == "node":
				selection = self.selection_context.get_selection(single=True);
				if selection != None:
					nodes = selection.navlist["nodes"];
					pasted = self.clipboard.paste(nodes);
					offset = PASTE_OFFSET * self.clipboard.paste_count;
					for node in pasted:
						node["position"][0] += offset;
						node["position"][1] += offset;
					if len(pasted) > 0:
						self.selection_context.select(NavlistEditor.ManipIndex(selection.navlist, nodes.index(pasted[-1])), exclusive=True);

		self.synchronize_manip();
		self.canvas_manip.tick();
		self.handle_events();

	def draw_gui(self):
		if self.navlists == None:
			return;

		self.place_mode = input_bool("Place mode", self.place_mode);

		selection = self.selection_context.get_selection(single=True);

		for idx, navlist in enumerate(self.navlists):
			selected = selection != None and selection.navlist is navlist;
			imgui.set_next_item_open(selected);
			label = navlist["name"] if navlist["name"] != "" else f"Navlist {idx}";
			node_open = imgui.tree_node(f"{label} ({idx})##{id(self.navlists)}{idx}");

			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("Delete"):
					self._delete_navlist(idx);
					self.selection_context.clear();
					imgui.close_current_popup();
				imgui.end_popup();
			self.trash.flush();

			if not node_open:
				continue;

			scenes.navlists.gui_draw(navlist);

			imgui.text("Nodes");
			nodes = navlist["nodes"];
			for node_idx, node in enumerate(nodes):
				node_selected = selected and selection.node_idx == node_idx;
				imgui.set_next_item_open(node_selected);
				node_row_open = imgui.tree_node(f"Node {node_idx}##{id(navlist)}{node_idx}");

				if imgui.begin_popup_context_item():
					if imgui.menu_item_simple("Move up") and node_idx > 0:
						nodes[node_idx-1], nodes[node_idx] = nodes[node_idx], nodes[node_idx-1];
						self.selection_context.select(NavlistEditor.ManipIndex(navlist, node_idx-1), exclusive=True);
						imgui.close_current_popup();
					if imgui.menu_item_simple("Move down") and node_idx < len(nodes)-1:
						nodes[node_idx+1], nodes[node_idx] = nodes[node_idx], nodes[node_idx+1];
						self.selection_context.select(NavlistEditor.ManipIndex(navlist, node_idx+1), exclusive=True);
						imgui.close_current_popup();
					if imgui.menu_item_simple("Insert after"):
						inserted = scenes.navlists.insert_node_after(navlist, node_idx);
						self.selection_context.select(NavlistEditor.ManipIndex(navlist, inserted), exclusive=True);
						imgui.close_current_popup();
					if imgui.menu_item_simple("Delete") and len(nodes) > 1:
						self.trash.trash_index(nodes, node_idx);
						self.selection_context.clear();
						imgui.close_current_popup();
					imgui.end_popup();
				self.trash.flush();

				if node_row_open:
					if not node_selected:
						self.selection_context.select(NavlistEditor.ManipIndex(navlist, node_idx), exclusive=True);
					scenes.navlists.gui_draw_node(node);
					imgui.tree_pop();

			imgui.tree_pop();

	def draw_canvas(self):
		if self.navlists == None:
			return;

		colour = (128, 255, 255);
		selection = self.selection_context.get_selection(single=True);
		selected_navlist = selection.navlist if selection != None else None;

		for navlist in self.navlists:
			is_selected = navlist is selected_navlist;
			scenes.navlists.canvas_draw(
				self.parent.canvas, navlist, colour,
				selected_node=selection.node_idx if is_selected else None,
				highlight=(0, 255, 255) if is_selected else None
			);

		if selected_navlist != None and selection.node_idx == None:
			self.parent.canvas.draw_aabb(scenes.navlists.get_aabb(selected_navlist), (255, 255, 255));

class SceneViewer:
	def __init__(self, parent):
		self.parent = parent;

		self.show_tiles = True;
		self.show_entities = True;
		self.show_decorations = True;

		self.show_grid = False;
		self.show_walls = True;
		self.show_boxes = False;
		self.show_gizmos = True;
	
	def draw_tilemaps(self, foreground):
		for tilemap in self.parent.scene["tilemaps"]:
			if tilemap["is_foreground"] == foreground:
				scenes.tilemaps.canvas_draw(self.parent.canvas, tilemap);

	def draw_entity(self, entity):
		prototype = AssetManager.search("prototype", entity["prototype"]);
		sprite = SpriteBank.search(prototype["sprite"], safe=False) if prototype != None else None;

		x, y = entity["position"];
		dx, dy = prototype["sprite_offset"] if prototype != None else (0, 0);

		if sprite != None:
			frame_idx = clamp(entity["frame_idx"], 0, sprite.frame_count-1);
			self.parent.canvas.draw_image(x+dx, y+dy, sprite.frame_images[frame_idx]);
		else:
			self.parent.canvas.draw_aabb(get_entity_aabb(entity), (255, 255, 0));

	def draw_entity_overlays(self):
		for entity in self.parent.scene["entities"]:
			prototype = AssetManager.search("prototype", entity["prototype"]);
			x, y = entity["position"];

			if prototype != None and self.show_boxes:
				if prototype["has_blocker"]:
					x0, y0, x1, y1 = prototype["blocker"];
					self.parent.canvas.draw_aabb((x0+x, y0+y, x1+x, y1+y), (255, 0, 0));
				if prototype["has_trigger"]:
					x0, y0, x1, y1 = prototype["trigger"];
					self.parent.canvas.draw_aabb((x0+x, y0+y, x1+x, y1+y), (0, 255, 0));

			if self.parent.selection_context.is_selected(entity):
				self.parent.canvas.draw_aabb(get_entity_aabb(entity), (255, 255, 255));
				self.parent.canvas.draw_circle(x, y, 4, (192, 192, 255));

	def draw_decoration_overlays(self):
		for decoration in self.parent.scene["decorations"]:
			if self.parent.decoration_editor.selection_context.is_selected(decoration):
				self.parent.canvas.draw_aabb(scenes.decorations.get_aabb(decoration), (255, 255, 255));

	def draw_world(self):
		bodies = [];

		if self.show_entities:
			for entity in self.parent.scene["entities"]:
				bodies.append((get_entity_body_key(entity), lambda e=entity: self.draw_entity(e)));

		if self.show_decorations:
			for decoration in self.parent.scene["decorations"]:
				bodies.append((scenes.decorations.get_body_key(decoration), lambda d=decoration: scenes.decorations.canvas_draw(self.parent.canvas, d)));

		bodies = sorted(bodies, key=lambda x: x[0]);
		for _, draw_body in bodies:
			draw_body();

	def draw_walls(self):
		if self.parent.scene["has_bounds"]:
			self.parent.canvas.draw_aabb(self.parent.scene["bounds"], (128, 0, 0), False);
		
		for wall in self.parent.scene["walls"]:
			colour = (255, 255, 0) if self.parent.wall_editor.selection_context.is_selected(wall) else (255, 0, 0);
			scenes.walls.canvas_draw(self.parent.canvas, wall, colour);
	
	def draw(self):
		self.parent.canvas.clear(tuple(self.parent.scene["background"]));

		if self.show_tiles:
			self.draw_tilemaps(False);
		if self.show_grid:
			self.parent.canvas_grid.draw_lines((64, 64, 64));
		self.parent.canvas.draw_guides((128, 128, 128));

		self.draw_world();

		if self.show_tiles:
			self.draw_tilemaps(True);

		if self.show_entities:
			self.draw_entity_overlays();
		if self.show_decorations:
			self.draw_decoration_overlays();
		if self.show_walls:
			self.draw_walls();

		if self.show_gizmos:
			self.parent.door_editor.draw();
			self.parent.navlist_editor.draw_canvas();

		if self.parent.edit_mode == EditMode.TILEMAP:
			self.parent.tilemap_editor.draw_canvas();

class SceneEditor:
	class SpawnPopup:
		def __init__(self, parent):
			self.parent = parent;
			self.is_open = False;
			self.prototype = "";
			self.position = None;
		
		def open(self):
			self.is_open = True;
			if self.parent.canvas_io.is_cursor_in_bounds():
				self.position = list(self.parent.canvas_io.get_cursor());
			else:
				self.position = [0, 0];

		def draw(self):
			if self.is_open:
				_, self.is_open = imgui.begin("Spawn", self.is_open);
				self.prototype = input_asset("##prototype", self.prototype, "prototype");
				if imgui.button("Spawn"):
					entity = AssetManager.get_tree("scene").search("entities").inmost.prototype();
					entity["name"] = "";
					entity["position"] = self.position;
					entity["prototype"] = self.prototype;
					self.parent.scene["entities"].append(entity);
					self.is_open = False;
				imgui.same_line();
				if imgui.button("Cancel"):
					self.is_open = False;
				imgui.end();
	
	def _load_scene(self, scene):		
		self.scene = scene;

		self.event_queue.clear();
		self.canvas_manip.clear();
		self.manip_registry.clear();

		self.selection_context.clear();
		
		self.tilemap_editor.on_load_scene();
		self.wall_editor.on_load_scene();
		self.decoration_editor.on_load_scene();
		self.navlist_editor.on_load_scene();

	def _is_scene_loaded(self):
		return self.scene in AssetManager.get_all("scene");

	def __init__(self):
		self.canvas_size = (1000, 720);
		self.canvas = Canvas(self.canvas_size[0], self.canvas_size[1], origin=(self.canvas_size[0]//2, self.canvas_size[1]//2));
		self.canvas_io = CanvasIO(self.canvas);
		self.canvas_grid = CanvasGrid(
			self.canvas,
		    16
		);

		self.event_queue = [];
		self.canvas_manip = CanvasManipulator(self.canvas_io, self.event_queue);
		self.manip_registry = CanvasManipRegistry();

		self.selection_context = SelectionContext();
		self.clipboard = Clipboard();
		self.trash = Trash(deferred=True);

		self.edit_mode = EditMode.ENTITIES;
		self.snap = True;
		self.entity_search = "";

		self.rename_target = None;
		self.rename_buffer = "";
		self.rename_pending = False;

		self.tilemap_editor = TilemapEditor(self);
		self.wall_editor = WallEditor(self);
		self.decoration_editor = DecorationEditor(self);
		self.door_editor = DoorEditor(self);
		self.navlist_editor = NavlistEditor(self);
		self.scene_viewer = SceneViewer(self);

		self.spawn_popup = SceneEditor.SpawnPopup(self);

		self._load_scene(AssetManager.get_first("scene"));

	def handle_events(self):
		while len(self.event_queue) > 0:
			event = self.event_queue.pop(0);

			if isinstance(event, CanvasManipClick):
				if event.eeid == None:
					self.selection_context.clear();
				else:
					entity = self.manip_registry.search(event.eeid);
					self.selection_context.select(entity, exclusive=True);
			
			if isinstance(event, CanvasManipDrag):
				if event.eeid != None:
					match event.signal:
						case CanvasManipDrag.Signal.TICK:
							entity = self.selection_context.get_selection(single=True);
							point = event.point;
							delta = event.delta;
							position = point[0]+delta[0], point[1]+delta[1];
							if self.snap:
								position = self.canvas_grid.snap_point(position);
							entity["position"] = position;
			
			if isinstance(event, CanvasManipViewDrag):
				CanvasManipulator.default_view_drag_handler(self.canvas, event);
	
	def get_entity_sprite(self, entity):
		prototype = AssetManager.search("prototype", entity["prototype"]);
		return SpriteBank.search(prototype["sprite"] if prototype != None else "null");
	
	def synchronize_manip(self):
		def make_shape(entity):
			aabb = get_entity_aabb(entity);
			return CanvasManipRect(aabb);
		shapes = [make_shape(x) for x in self.scene["entities"]];
		keys = [get_entity_body_key(x) for x in self.scene["entities"]];
		
		self.manip_registry.update(self.scene["entities"], shapes, keys);
		self.canvas_manip.synchronize(self.manip_registry);
	
	def paste_entities(self):
		pasted = self.clipboard.paste(self.scene["entities"]);
		offset = PASTE_OFFSET * self.clipboard.paste_count;

		if len(pasted) > 0:
			self.selection_context.clear();
		for entity in pasted:
			x, y = entity["position"];
			position = (x+offset, y+offset);
			if self.snap:
				position = self.canvas_grid.snap_point(position);
			entity["position"] = [int(position[0]), int(position[1])];
			self.selection_context.select(entity);

	def begin_rename(self, entity):
		self.rename_target = entity;
		self.rename_buffer = entity["name"];
		# Popup IDs hash against the ID stack, so the popup must be opened
		# from window level rather than from inside the context menu.
		self.rename_pending = True;

	def draw_rename_modal(self):
		modal_id = "Rename entity";
		if self.rename_pending:
			imgui.open_popup(modal_id);
			self.rename_pending = False;

		if self.rename_target == None:
			return;

		visible, _ = imgui.begin_popup_modal(modal_id, None, imgui.WindowFlags_.always_auto_resize);
		if not visible:
			self.rename_target = None;
			return;

		old_name = self.rename_target["name"];

		if imgui.is_window_appearing():
			imgui.set_keyboard_focus_here();
		imgui.set_next_item_width(256);
		submitted, self.rename_buffer = imgui.input_text(
			"##rename", self.rename_buffer, imgui.InputTextFlags_.enter_returns_true
		);

		new_name = self.rename_buffer.strip();
		collision = new_name != old_name and any(e["name"] == new_name for e in self.scene["entities"]);
		valid = len(new_name) > 0 and not collision;

		if collision:
			imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "Name already in use");
		elif len(new_name) == 0:
			imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "Name cannot be empty");

		imgui.begin_disabled(not valid);
		commit = imgui.button("Rename") or (submitted and valid);
		imgui.end_disabled();
		imgui.same_line();
		cancel = imgui.button("Cancel") or imgui.is_key_pressed(imgui.Key.escape);

		if commit:
			self.rename_target["name"] = new_name;
			self.rename_target = None;
			imgui.close_current_popup();
		elif cancel:
			self.rename_target = None;
			imgui.close_current_popup();

		imgui.end_popup();

	def draw_menu_bar(self):
		if imgui.begin_menu_bar():

			if imgui.begin_menu("Scene"):
				if imgui.begin_menu("Open"):
					scenes = AssetManager.get_all("scene");
					scene_last = self.scene;
					for scene in scenes:
						if imgui.menu_item_simple(scene["name"]):
							self.scene = scene;
					if self.scene != scene_last:
						self._load_scene(self.scene);
					imgui.end_menu();
				imgui.end_menu();
			
			if imgui.begin_menu("View"):
				_, self.scene_viewer.show_tiles = imgui.menu_item("Tiles", "", self.scene_viewer.show_tiles);
				_, self.scene_viewer.show_entities = imgui.menu_item("Entities", "", self.scene_viewer.show_entities);
				_, self.scene_viewer.show_decorations = imgui.menu_item("Decorations", "", self.scene_viewer.show_decorations);
				_, self.scene_viewer.show_boxes = imgui.menu_item("Boxes", "", self.scene_viewer.show_boxes);
				_, self.scene_viewer.show_walls = imgui.menu_item("Walls", "", self.scene_viewer.show_walls);
				_, self.scene_viewer.show_gizmos = imgui.menu_item("Gizmos", "", self.scene_viewer.show_gizmos);
				_, self.scene_viewer.show_grid = imgui.menu_item("Grid", "", self.scene_viewer.show_grid);
				imgui.end_menu();
			
			if imgui.begin_menu("Grid"):
				imgui.set_next_item_width(64);
				self.canvas_grid.size = input_int("Size", self.canvas_grid.size, style=EEGUIIntStyle.SLIDER, low_bound=2, high_bound=16);
				self.snap = input_bool("Snap", self.snap);
				imgui.end_menu();
			
			imgui.end_menu_bar();		
	
	def gui_draw_entities(self):
		_, self.entity_search = imgui.input_text("Search", self.entity_search);

		for entity in self.scene["entities"]:
			name = entity["name"] if len(entity["name"]) > 0 else str(id(entity));
			if len(self.entity_search) > 0 and self.entity_search not in name:
				continue;

			sprite = self.get_entity_sprite(entity);

			imgui.set_next_item_open(self.selection_context.is_selected(entity));
			node_open = imgui.tree_node(f"{name}####{id(entity)}");

			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("Rename"):
					self.begin_rename(entity);
					imgui.close_current_popup();
				if imgui.menu_item_simple("Delete"):
					self.trash.trash_item(self.scene["entities"], entity);
					imgui.close_current_popup();
				imgui.end_popup();
			
			if node_open:
				self.selection_context.select(entity, exclusive=True);
				
				entity["name"] = input_string("Name", entity["name"]);
				imgui.same_line();
				entity["enabled"] = input_bool("##enabled", entity["enabled"]);
				entity["prototype"] = input_asset("Prototype", entity["prototype"], "prototype");
				if len(entity["prototype"]) > 0 and len(entity["name"]) <= 0:
					entity["name"] = entity["prototype"];

				entity["frame_idx"] = input_int("Frame", entity["frame_idx"], EEGUIIntStyle.SLIDER, 0, sprite.frame_count-1);
				
				if imgui.tree_node("Script data"):
					for entry in entity["script_data"]:
						if not imgui.tree_node(entry["script"]):
							continue;
						for datum in entry["data"]:
							sd = scripts.ScriptDatum(datum["signature"]["key"], datum["signature"]["type"]);
							if imgui.tree_node(f"{sd.key}##{entry["script"]}"):
								datum["value"] = typed_input(f"##{sd.key}##{entry["script"]}", sd.type, datum["value"]);
								imgui.tree_pop();
						imgui.tree_pop();
					if imgui.button("Reset to defaults"):
						entity["script_data"] = [];
					imgui.tree_pop();
				imgui.tree_pop();
	
	def gui_draw_properties_editor(self):
		self.scene["has_background"] = input_bool("Has background", self.scene["has_background"]);
		if self.scene["has_background"]:
			self.scene["background"] = input_colour("Background", self.scene["background"]);
		self.scene["has_bounds"] = input_bool("Has bounds", self.scene["has_bounds"]);
		if self.scene["has_bounds"]:
			self.scene["bounds"] = input_aabb("Bounds", self.scene["bounds"]);
		self.scene["free_camera"] = input_bool("Free camera", self.scene["free_camera"]);

	def draw(self):
		self.draw_menu_bar();

		if not self._is_scene_loaded():
			return;

		self.canvas_io.tick();
		self.synchronize_manip();
		
		for entity in self.scene["entities"]:
			rectify_entity_script_data(entity);

		def run_left_panel(panel_tick):
			imgui.begin_child(
				"left-panel",
				imgui.ImVec2((imgui.get_content_region_avail().x - self.canvas.width) * 0.9, imgui.get_content_region_avail().y),
				0, 0
			);
			panel_tick();
			imgui.end_child();
		
		def entities_tick():
			if InputManager.is_command(glfw.KEY_C):
				self.clipboard.copy(self.selection_context.get_selection(single=True), copy_mode=Clipboard.CopyMode.DEEP, exclusive=True);
			if InputManager.is_command(glfw.KEY_V):
				self.paste_entities();
			
			if InputManager.is_command(glfw.KEY_A):
				self.spawn_popup.open();
			if InputManager.is_command(glfw.KEY_D):
				selection = self.selection_context.get_selection(single=True);
				if selection != None:
					self.trash.trash_item(self.scene["entities"], selection);
			
			self.spawn_popup.draw();
			self.draw_rename_modal();

			self.canvas_manip.tick();
			self.handle_events();

			self.gui_draw_entities();
			self.trash.flush();

		def tilemap_tick():
			self.tilemap_editor.tick();
			self.tilemap_editor.draw_gui();
		
		def walls_tick():
			self.wall_editor.tick();
			self.wall_editor.draw_gui();
		
		def doors_tick():
			self.door_editor.logic();
			self.door_editor.gui();
		
		def navlists_tick():
			self.navlist_editor.logic();
			self.navlist_editor.draw_gui();
		
		def decorations_tick():
			self.decoration_editor.tick();
			self.decoration_editor.draw_gui();
		
		def properties_tick():
			self.gui_draw_properties_editor();
		
		match self.edit_mode:
			case EditMode.ENTITIES:
				run_left_panel(entities_tick);
			case EditMode.TILEMAP:
				run_left_panel(tilemap_tick);
			case EditMode.WALLS:
				run_left_panel(walls_tick);
			case EditMode.DOORS:
				run_left_panel(doors_tick);
			case EditMode.NAVLISTS:
				run_left_panel(navlists_tick);
			case EditMode.DECORATIONS:
				run_left_panel(decorations_tick);
			case EditMode.PROPERTIES:
				run_left_panel(properties_tick);	

		imgui.same_line();
		imgui.begin_child(
			"main-panel",
			imgui.ImVec2(imgui.get_content_region_avail().x, imgui.get_content_region_avail().y),
			0, 0
		);

		if imgui.begin_tab_bar("edit-mode"):
			for value in EditMode:
				tab_visible, tab_open = imgui.begin_tab_item(value.name);
				if tab_visible:
					self.edit_mode = value;
					imgui.end_tab_item();
			imgui.end_tab_bar();

		self.scene_viewer.draw();
		self.canvas.render(gui_id="canvas");
		
		imgui.end_child();
