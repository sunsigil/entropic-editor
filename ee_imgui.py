import OpenGL;
OpenGL.FULL_LOGGING = True;
from OpenGL.GL import *;
from imgui_bundle import imgui;
from enum import Enum;

import ee_context;
from ee_assets import AssetManager;
from ee_tool_window import ToolWindowRegistry;
from ee_file_explorer import FileExplorer;
from ee_asset_explorer import AssetExplorer;
import ee_types;
import ee_sprites;

# Not Even Input

class EEGUITooltip:
	tooltip = None;

	def ping():
		if EEGUITooltip.tooltip == None:
			return;
		if imgui.is_item_hovered():
			imgui.set_tooltip(str(EEGUITooltip.tooltip));
		EEGUITooltip.tooltip = None;

class EEGUIContextMenu:
	gui_id = None;

	def _make_id(gui_id):
		return f"##context-menu-{gui_id}";

	def ping(gui_id):
		window_id = EEGUIContextMenu._make_id(gui_id);
		if imgui.is_popup_open(window_id):
			return;
	
		if imgui.begin_popup_context_item(window_id):
			imgui.open_popup(window_id);
			EEGUIContextMenu.gui_id = gui_id;
			imgui.end_popup();

	def begin(gui_id):
		if EEGUIContextMenu.gui_id == None or EEGUIContextMenu.gui_id != gui_id:
			return;
		return imgui.begin_popup(EEGUIContextMenu._make_id(gui_id));

# Even More Primitive

def eegui_combo(gui_id, value, values, fmt=lambda x: x):
	if imgui.begin_combo(str(gui_id), str(fmt(value))):
		for candidate in values:
			selected = candidate == value;
			if imgui.selectable(str(fmt(candidate)), selected)[0]:
				value = candidate;
			if selected:
				imgui.set_item_default_focus();
		imgui.end_combo();
	EEGUITooltip.ping();
	EEGUIContextMenu.ping(gui_id);
	return value;

# Primitives

class EEGUIIntStyle(Enum):
	DEFAULT = 0
	SLIDER = 1

def eegui_input_int(gui_id, value, style=EEGUIIntStyle.DEFAULT, low_bound=None, high_bound=None):
	match style:
		case EEGUIIntStyle.DEFAULT:
			_, value = imgui.input_int(str(gui_id), int(value));
			if low_bound != None:
				value = max(value, low_bound);
			if high_bound != None:
				value = min(value, high_bound);
		case EEGUIIntStyle.SLIDER:
			_, value = imgui.slider_int(str(gui_id), value, low_bound, high_bound);
	EEGUITooltip.ping();
	EEGUIContextMenu.ping(gui_id);
	return value;

def eegui_input_float(gui_id, value):
	_, value = imgui.input_float(str(gui_id), value);
	EEGUITooltip.ping();
	EEGUIContextMenu.ping(gui_id);
	return value;

def eegui_input_bool(gui_id, value):
	_, value = imgui.checkbox(str(gui_id), bool(value));
	EEGUITooltip.ping();
	EEGUIContextMenu.ping(gui_id);
	return value;

def eegui_input_string(gui_id, value):
	_, value = imgui.input_text(str(gui_id), str(value));
	EEGUITooltip.ping();
	EEGUIContextMenu.ping(gui_id);
	return value;

def eegui_input_colour(gui_id, value):
	r, g, b = value;
	_, (r, g, b) = imgui.color_edit3(str(gui_id), (r/255, g/255, b/255));
	EEGUITooltip.ping();
	EEGUIContextMenu.ping(gui_id);
	return int(r*255), int(g*255), int(b*255);

def eegui_input_any(gui_id, value):
	value = eegui_input_string(gui_id, value);
	return value;

def eegui_input_vec2(gui_id, value):
	_, value = imgui.input_int2(gui_id, [int(value[0]), int(value[1])]);
	EEGUIContextMenu.ping(gui_id);
	return value;

# Enums

class EEGUIEnumStyle(Enum):
	COMBO = 0
	RADIO_BUTTONS = 1

def eegui_input_enum(gui_id, value, values, style=EEGUIEnumStyle.COMBO):
	enum_class = values if isinstance(values, type) and issubclass(values, Enum) else None;
	if enum_class != None:
		value = value.name;
		values = [x.name for x in values];	
	
	match style:
		case EEGUIEnumStyle.COMBO:
			value = eegui_combo(gui_id, value, values);
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

# Flags

def eegui_input_flags(gui_id, value, values):
	for candidate in values:
		_, included = imgui.checkbox(candidate, candidate in value);
		if included and not candidate in value:
			value.append(candidate);
		elif not included and candidate in value:
			value.remove(candidate);
	EEGUITooltip.ping();
	EEGUIContextMenu.ping(gui_id);
	return value;

def eegui_input_file(gui_id, value, pattern, directory=None, asset_type=None):
	value = eegui_input_string(gui_id, value);

	imgui.same_line();
	imgui.push_id(gui_id);

	explorer = ToolWindowRegistry.lookup(FileExplorer);
	if explorer.is_open():
		if explorer.get().is_targeting(gui_id):
			harvest = explorer.get_result();
			value = harvest if harvest != None else value;
	else:
		if imgui.button("Browse"):
			explorer.open();
			if directory == None:
				if asset_type != None:
					directory = AssetManager.get_document(asset_type).directory;
				else:
					directory = ee_context.get().directory;
			explorer.get().configure(gui_id, directory, pattern, asset_type);
	
	imgui.pop_id();

	return value;

# Special Data

def eegui_input_asset(gui_id, value, asset_type):
	value = eegui_input_string(gui_id, value);

	imgui.same_line();
	imgui.push_id(gui_id);

	explorer = ToolWindowRegistry.lookup(AssetExplorer);
	if explorer.is_open():
		if explorer.get().is_targeting(gui_id):
			harvest = explorer.get_result();
			value = harvest if harvest != None else value;
	else:
		if imgui.button("Browse"):
			explorer.open();
			explorer.get().configure(gui_id, asset_type);
	
	imgui.pop_id();

	return value;

# Structured Data

def eegui_typed_input(gui_id, T, value, previews=False, tooltip=False):
	gui_id = str(gui_id);

	if tooltip:
		EEGUITooltip.tooltip = T;

	if isinstance(T, ee_types.Object):
		node_open = imgui.tree_node(gui_id);
		EEGUITooltip.ping();
		EEGUIContextMenu.ping(gui_id);

		if node_open:
			for element in T.elements:
				if element.name in value:
					value[element.name] = eegui_typed_input(element.name, element.T, value[element.name], previews, tooltip);
			imgui.tree_pop();

	if isinstance(T, ee_types.List):
		node_open = imgui.tree_node(gui_id);
		EEGUITooltip.ping();
		EEGUIContextMenu.ping(gui_id);
		if EEGUIContextMenu.begin(gui_id):
			if imgui.menu_item_simple("Add"):
				value.append(T.T.prototype());
			imgui.end_popup();

		if node_open:
			trash = [];

			N = len(value);
			for i in range(N):
				value[i] = eegui_typed_input(f"[{i}]", T.T, value[i]);
				if EEGUIContextMenu.begin(f"[{i}]"):
					if imgui.menu_item_simple("Delete"):
						trash.append(i);
					imgui.end_popup();
			
			for i in trash:
				del value[i];
			trash = [];

			imgui.tree_pop();
	
	if isinstance(T, ee_types.Asset):
		if previews:
			match T.name:
				case "sprite":
					ee_sprites.SpritePreview.draw(value);
		value = eegui_input_asset(gui_id, value, T.name);
	
	if isinstance(T, ee_types.File):
		directory = None;
		if T.pattern == "*.png":
			if previews:
				ee_sprites.SpritePreview.draw(value);
			directory = ee_context.get().directory/"assets/sprites";
		value = eegui_input_file(gui_id, value, T.pattern, directory=directory);
	
	if isinstance(T, ee_types.Flags):
		value = eegui_input_flags(gui_id, value, T.values);
	if isinstance(T, ee_types.Enum):
		value = eegui_input_enum(gui_id, value, T.values);
	if isinstance(T, ee_types.Any):
		value = eegui_input_any(gui_id, value);
	if isinstance(T, ee_types.Vec2):
		value = eegui_input_vec2(gui_id, value);
	if isinstance(T, ee_types.Colour):
		value = eegui_input_colour(gui_id, value);
	if isinstance(T, ee_types.String):
		value = eegui_input_string(gui_id, value);
	if isinstance(T, ee_types.Bool):
		value = eegui_input_bool(gui_id, value);
	if isinstance(T, ee_types.Float):
		value = eegui_input_float(gui_id, value);
	if isinstance(T, ee_types.Int):
		value = eegui_input_int(gui_id, value);

	return value;

# External to the type system

def eegui_input_aabb(gui_id, value, mode="xyxy"):
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
			value = [x0, y0, x0+w, x0+h];
	imgui.end_group();
	EEGUIContextMenu.ping(gui_id);
	return value;

# Layout

def eegui_begin_column(imgui_id, w=None):
	w = imgui.get_content_region_avail().x if w == None else w;
	h = imgui.get_content_region_avail().y;
	imgui.begin_child(
		str(imgui_id),
		imgui.ImVec2(w, h),
		0, 0
	);
def eegui_end_column():
	imgui.end_child();
	imgui.same_line();
	