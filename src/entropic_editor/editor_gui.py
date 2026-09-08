import OpenGL;
OpenGL.FULL_LOGGING = True;
from OpenGL.GL import *;
from imgui_bundle import imgui;
from enum import Enum;

import context;
import sprites;
import asset_types;
import cowtools;

from assets import AssetManager;
from tool_window import ToolWindowRegistry;
import file_explorer;
import asset_explorer;
from text_editor import TextEditor;

# Not Actually GUI

def get_anchor(gui_id):
	if not "####" in gui_id:
		return gui_id;
	idx = gui_id.find("####");
	anchor = gui_id[idx+4:];
	return anchor;

class Tooltip:
	tooltip = None;

	def ping():
		if Tooltip.tooltip == None:
			return;
		if imgui.is_item_hovered():
			imgui.set_tooltip(str(Tooltip.tooltip));
		Tooltip.tooltip = None;

class ContextMenu:
	gui_id = None;
	pending_frame = -1;

	def _make_id(gui_id):
		return f"##context-menu-{gui_id}";

	# ping() only records that the last item was right-clicked. The popup is
	# opened and drawn in begin(), so open_popup and begin_popup always run
	# under the same ID stack. Opening it here would fail whenever the item
	# is an expanded tree node, since tree_node pushes an ID until tree_pop
	# and begin() is usually called after that.
	def ping(gui_id):
		if imgui.is_item_hovered(imgui.HoveredFlags_.allow_when_blocked_by_popup) and imgui.is_mouse_released(imgui.MouseButton_.right):
			ContextMenu.gui_id = gui_id;
			ContextMenu.pending_frame = imgui.get_frame_count();

	def begin(gui_id):
		if ContextMenu.gui_id != gui_id:
			return False;
		window_id = ContextMenu._make_id(gui_id);
		# A ping with no matching begin() would otherwise stay pending forever.
		if imgui.get_frame_count() - ContextMenu.pending_frame <= 1:
			imgui.open_popup(window_id);
			ContextMenu.pending_frame = -1;
		return imgui.begin_popup(window_id);
	
# Even More Primitive

def combo(gui_id, value, values, fmt=lambda x: x):
	if imgui.begin_combo(str(gui_id), str(fmt(value))):
		for candidate in values:
			selected = candidate == value;
			if imgui.selectable(str(fmt(candidate)), selected)[0]:
				value = candidate;
			if selected:
				imgui.set_item_default_focus();
		imgui.end_combo();
	ContextMenu.ping(gui_id);
	Tooltip.ping();
	return value;

# Custom Widgets

def edit_button(gui_id, size=(16,16)):
	edit = sprites.SpriteBank.search("editor_edit");
	return imgui.image_button(f"##{gui_id}", imgui.ImTextureRef(edit.frame_textures[0]), size);

# Primitives

class EEGUIIntStyle(Enum):
	DEFAULT = 0
	SLIDER = 1

def input_int(gui_id, value, style=EEGUIIntStyle.DEFAULT, low_bound=None, high_bound=None):
	match style:
		case EEGUIIntStyle.DEFAULT:
			_, value = imgui.input_int(str(gui_id), int(value) if value != None else 0);
			if low_bound != None:
				value = max(value, low_bound);
			if high_bound != None:
				value = min(value, high_bound);
		case EEGUIIntStyle.SLIDER:
			_, value = imgui.slider_int(str(gui_id), value, low_bound, high_bound);
	ContextMenu.ping(gui_id);
	Tooltip.ping();
	return value;

def input_float(gui_id, value):
	_, value = imgui.input_float(str(gui_id), value);
	ContextMenu.ping(gui_id);
	Tooltip.ping();
	return value;

def input_bool(gui_id, value):
	_, value = imgui.checkbox(str(gui_id), bool(value));
	ContextMenu.ping(gui_id);
	Tooltip.ping();
	return value;

def input_string(gui_id, value, long=False):
	text_id = str(gui_id);
	_, value = imgui.input_text(text_id, str(value));
	ContextMenu.ping(gui_id);
	Tooltip.ping();
	
	if long:
		imgui.same_line();
		win_id = imgui.get_id(gui_id);
		win = ToolWindowRegistry.search(TextEditor).window(win_id);

		hide_id = gui_id.startswith("##");		
		if edit_button(gui_id if hide_id else f"##{gui_id}") and win == None:
			win = ToolWindowRegistry.search(TextEditor).open(win_id);
			win.configure(gui_id, value);
		if win != None:
			value = win.get_text();
	
	return value;

def input_any(gui_id, value):
	value = input_string(gui_id, value);
	return value;



# Enums and Flags

class EEGUIEnumStyle(Enum):
	COMBO = 0
	RADIO_BUTTONS = 1

def input_enum(gui_id, value, values, style=EEGUIEnumStyle.COMBO):
	enum_class = values if isinstance(values, type) and issubclass(values, Enum) else None;
	if enum_class != None:
		value = value.name;
		values = [x.name for x in values];	
	
	match style:
		case EEGUIEnumStyle.COMBO:
			value = combo(gui_id, value, values);
		case EEGUIEnumStyle.RADIO_BUTTONS:
			selected_idx = values.index(value) if value in values else -1;
			for idx,v in enumerate(values):
				_, selected_idx = imgui.radio_button(v, selected_idx, idx);
				imgui.same_line();
			imgui.new_line();
			value = values[selected_idx] if selected_idx != -1 else value;
	
	if enum_class != None:
		value = next((x for x in enum_class if x.name == value), None);
	return value;

def input_flags(gui_id, value, values):
	for candidate in values:
		_, included = imgui.checkbox(candidate, candidate in value);
		if included and not candidate in value:
			value.append(candidate);
		elif not included and candidate in value:
			value.remove(candidate);
	ContextMenu.ping(gui_id);
	Tooltip.ping();
	return value;

# Special Data

def input_file(gui_id, value, pattern, directory=None, asset_type=None, return_absolute=False):
	value = input_string(gui_id, value);

	imgui.same_line();
	browse = imgui.button(f"Browse##{gui_id}");

	win_id = imgui.get_id(gui_id);
	win = ToolWindowRegistry.search(file_explorer.FileExplorer).window(win_id);
	if win != None:
		harvest = win.get_result();
		value = harvest if harvest != None else value;
	else:
		if browse:
			win = ToolWindowRegistry.search(file_explorer.FileExplorer).open(win_id);
			if directory == None:
				if asset_type != None:
					directory = AssetManager.get_document(asset_type).directory;
				else:
					directory = context.get().game_directory;
			win.configure(directory, pattern, asset_type, return_absolute);

	return value;

def input_asset(gui_id, value, asset_type):
	value = input_string(gui_id, value);

	imgui.same_line();
	browse = imgui.button(f"Browse##{gui_id}");

	win_id = imgui.get_id(gui_id);
	win = ToolWindowRegistry.search(asset_explorer.AssetExplorer).window(win_id);
	if win != None:
		harvest = win.get_result();
		value = harvest if harvest != None else value;
	else:
		if browse:
			win = ToolWindowRegistry.search(asset_explorer.AssetExplorer).open(win_id);
			win.configure(asset_type);

	return value;

def input_sprite(gui_id, value, size=(64, 64)):
	sprite = sprites.SpriteBank.search(value);
	w, h = size;

	clicked = imgui.image_button(gui_id, imgui.ImTextureRef(sprite.frame_textures[0]), imgui.ImVec2(w, h));

	win_id = imgui.get_id(gui_id);
	win = ToolWindowRegistry.search(asset_explorer.AssetExplorer).window(win_id);
	if win != None:
		harvest = win.get_result();
		value = harvest if harvest != None else value;
	else:
		if clicked:
			win = ToolWindowRegistry.search(asset_explorer.AssetExplorer).open(win_id);
			win.configure("sprite");

	return value;

# Structured Data

def typed_input(gui_id, T, value, previews=False, tooltip=False):
	if getattr(T, "read_only", False):
		typed_display(gui_id, T, value, previews, tooltip);
		return;
	
	gui_id = str(gui_id);
	anchor = get_anchor(gui_id);

	if tooltip:
		Tooltip.tooltip = T;

	if isinstance(T, asset_types.Object):
		node_open = imgui.tree_node(gui_id);
		ContextMenu.ping(gui_id);
		Tooltip.ping();

		if node_open:
			if previews:
				if "path" in value and "frames" in value:
					sprites.SpritePreview.draw(None, value["path"], value["frames"], show_dimensions=True);

			for key,element in T.elements.items():
				if key in value:
					if getattr(element, "read_only", False):
						typed_display(f"{key}##{anchor}", element, value[key], previews, tooltip);
					else:
						value[key] = typed_input(f"{key}##{anchor}", element, value[key], previews, tooltip);
			imgui.tree_pop();

	if isinstance(T, asset_types.List):
		node_open = imgui.tree_node(gui_id);
		ContextMenu.ping(gui_id);
		Tooltip.ping();
		if ContextMenu.begin(gui_id):
			if imgui.menu_item_simple("Add"):
				value.append(T.T.prototype());
			imgui.end_popup();

		if node_open:
			N = len(value);

			if getattr(T, "read_only", False):
				for i in range(N):
					typed_display(f"[{i}]##{anchor}", T.T, value[i], previews, tooltip);
			else:
				trash = [];
				for i in range(N):
					value[i] = typed_input(f"[{i}]##{anchor}", T.T, value[i], previews, tooltip);
					if ContextMenu.begin(f"[{i}]##{anchor}"):
						if imgui.menu_item_simple("Delete"):
							trash.append(i);
						imgui.end_popup();
				for i in trash:
					del value[i];
				trash = [];

			imgui.tree_pop();
	
	if isinstance(T, asset_types.Asset):
		if previews:
			match T.name:
				case "sprite":
					sprites.SpritePreview.draw(value, show_dimensions=True);
		value = input_asset(gui_id, value, T.name);
	
	if isinstance(T, asset_types.File):
		directory = None;
		if T.pattern == "*.png":
			directory = context.get().game_directory/"assets/sprites";			
		value = input_file(gui_id, value, T.pattern, directory=directory);
	
	if isinstance(T, asset_types.Flags):
		value = input_flags(gui_id, value, T.values);
	if isinstance(T, asset_types.Enum):
		value = input_enum(gui_id, value, T.values);
	if isinstance(T, asset_types.Any):
		value = input_any(gui_id, value);
	if isinstance(T, asset_types.String):
		value = input_string(gui_id, value, hasattr(T, "code") and T.code);
	if isinstance(T, asset_types.Bool):
		value = input_bool(gui_id, value);
	if isinstance(T, asset_types.Float):
		value = input_float(gui_id, value);
	if isinstance(T, asset_types.Int):
		value = input_int(gui_id, value);

	return value;

def typed_display(gui_id, T, value, previews=False, tooltip=False):
	gui_id = str(gui_id);
	anchor = get_anchor(gui_id);

	if tooltip:
		Tooltip.tooltip = T;

	if isinstance(T, asset_types.Object):
		node_open = imgui.tree_node(gui_id);
		Tooltip.ping();

		if node_open:
			for key, element in T.elements.items():
				if key in value:
					typed_display(f"{key}##{anchor}", element, value[key], previews, tooltip);
			imgui.tree_pop();

	if isinstance(T, asset_types.List):
		node_open = imgui.tree_node(gui_id);
		Tooltip.ping();

		if node_open:
			for i in range(len(value)):
				typed_display(f"[{i}]##{anchor}", T.T, value[i], previews, tooltip);
			imgui.tree_pop();
	
	if isinstance(T, asset_types.Asset):
		if previews:
			match T.name:
				case "sprite":
					sprites.SpritePreview.draw(value);
		imgui.text(value);
	
	if isinstance(T, asset_types.File):
		imgui.text(value);
	
	if isinstance(T, asset_types.Flags):
		imgui.text(" | ".join(value));
	if isinstance(T, asset_types.Enum):
		imgui.text(value);
	if isinstance(T, asset_types.Any):
		imgui.text(value);
	if isinstance(T, asset_types.String):
		imgui.text(value);
	if isinstance(T, asset_types.Bool):
		input_bool(gui_id, value);
	if isinstance(T, asset_types.Float):
		imgui.text(str(value));
	if isinstance(T, asset_types.Int):
		imgui.text(str(value));

# External to the type system

def input_vec2(gui_id, value):
	_, value = imgui.input_int2(gui_id, [int(value[0]), int(value[1])]);
	ContextMenu.ping(gui_id);
	return value;

def input_aabb(gui_id, value, mode="xyxy"):
	imgui.begin_group();
	match mode:
		case "xyxy":
			value[:2] = imgui.input_int2(f"X0 Y0##{gui_id}", [int(value[0]), int(value[1])])[1];
			value[2:] = imgui.input_int2(f"X1 Y1##{gui_id}", [int(value[2]), int(value[3])])[1];
		case "xywh":
			x0, y0, x1, y1 = value;
			w, h = x1-x0, y1-y0;
			x0, y0 = imgui.input_int2(f"X Y##{gui_id}", [int(x0), int(y0)])[1];
			w, h = imgui.input_int2(f"W H##{gui_id}", [int(w), int(h)])[1];
			value = [x0, y0, x0+w, y0+h];
	imgui.end_group();
	ContextMenu.ping(gui_id);
	return value;

def input_orientation(gui_id, value):
	arrow = sprites.SpriteBank.search("editor_arrow");
	orientations = [
		-1, 2, -1,
		3, 0, 1,
		-1, 4, -1
	];

	imgui.text(gui_id);
	
	imgui.same_line();
	imgui.push_id(gui_id);
	imgui.begin_group();
	imgui.push_style_var(imgui.StyleVar_.frame_padding, imgui.ImVec2(0, 0));
	for y in range(3):
		for x in range(3):
			if x > 0:
				imgui.same_line();
			cell_idx = y*3+x;
			cell_orientation = orientations[cell_idx];
			if cell_orientation == -1:
				imgui.dummy(imgui.ImVec2(16, 16));
			else:
				tint = (0.5, 0.5, 0.5, 1) if cell_orientation == value else (1, 1, 1, 1);
				if imgui.image_button(f"##{cell_orientation}", imgui.ImTextureRef(arrow.frame_textures[cell_orientation]), (16, 16), tint_col=tint):
					value = cell_orientation;
	imgui.pop_style_var();
	imgui.end_group();
	imgui.pop_id();	

	return value;

def input_colour(gui_id, value):
	r, g, b = value;
	_, (r, g, b) = imgui.color_edit3(str(gui_id), (r/255, g/255, b/255));
	ContextMenu.ping(gui_id);
	Tooltip.ping();
	return int(r*255), int(g*255), int(b*255);

# Layout

def begin_column(imgui_id, w=None):
	w = imgui.get_content_region_avail().x if w == None else w;
	h = imgui.get_content_region_avail().y;
	imgui.begin_child(
		str(imgui_id),
		imgui.ImVec2(w, h),
		0, 0
	);
def end_column():
	imgui.end_child();
	imgui.same_line();
	