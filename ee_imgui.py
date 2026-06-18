import OpenGL;
OpenGL.FULL_LOGGING = True;
from OpenGL.GL import *;
from imgui_bundle import imgui;
from ee_assets import AssetManager;
from ee_tool_window import ToolWindowRegistry;
from ee_file_explorer import FileExplorer;
from ee_asset_explorer import AssetExplorer;
import ee_context;
from enum import Enum;
import ee_types;
import ee_sprites;

# Not Even Input

class EEGUITooltip:
	enabled = True;
	tooltip = None;

	def ping():
		if not EEGUITooltip.enabled:
			return;
		if EEGUITooltip.tooltip == None:
			return;
		if imgui.is_item_hovered():
			imgui.set_tooltip(str(EEGUITooltip.tooltip));

class EEGUIContextMenu:
	enabled = True;
	gui_id = None;

	def _make_id(gui_id):
		return f"##context-menu-{gui_id}";

	def ping(gui_id):
		if not EEGUIContextMenu.enabled:
			return;
	
		window_id = EEGUIContextMenu._make_id(gui_id);
		if imgui.is_popup_open(window_id):
			return;
	
		if imgui.begin_popup_context_item(window_id):
			imgui.open_popup(window_id);
			EEGUIContextMenu.gui_id = gui_id;
			imgui.end_popup();

	def begin(gui_id):
		if not EEGUIContextMenu.enabled:
			return;
		if EEGUIContextMenu.gui_id == None or EEGUIContextMenu.gui_id != gui_id:
			return;
		return imgui.begin_popup(EEGUIContextMenu._make_id(gui_id));

# Even More Primitive

def eegui_selector(gui_id, value, values, fmt=lambda x: x):
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

def eegui_input_int(gui_id, value):
	_, value = imgui.input_int(str(gui_id), value);
	EEGUITooltip.ping();
	EEGUIContextMenu.ping(gui_id);
	return value;

def eegui_input_float(gui_id, value):
	_, value = imgui.input_float(str(gui_id), value);
	EEGUITooltip.ping();
	EEGUIContextMenu.ping(gui_id);
	return value;

def eegui_input_bool(gui_id, value):
	_, value = imgui.checkbox(str(gui_id), value);
	EEGUITooltip.ping();
	EEGUIContextMenu.ping(gui_id);
	return value;

def eegui_input_string(gui_id, value):
	_, value = imgui.input_text(str(gui_id), value);
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

# Enums

def eegui_input_enum(gui_id, value, values):
	if isinstance(values, Enum):
		values = [x for x in values];
	value = eegui_selector(gui_id, value, values);
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
					directory = ee_context.env["game_path"];
			explorer.get().configure(gui_id, directory, pattern, asset_type);
	
	imgui.pop_id();

	return value;

# Special Data

def eegui_input_assset(gui_id, value, asset_type):
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

def eegui_typed_input(gui_id, T, value, pretty=False):
	gui_id = str(gui_id);

	EEGUITooltip.tooltip = T;

	if isinstance(T, ee_types.Object):
		node_open = imgui.tree_node(gui_id);
		EEGUITooltip.ping();
		EEGUIContextMenu.ping(gui_id);

		if node_open:
			for element in T.elements:
				if element.name in value:
					value[element.name] = eegui_typed_input(element.name, element.T, value[element.name], pretty);
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
		if pretty:
			match T.name:
				case "sprite":
					ee_sprites.SpritePreview.draw(value);
		value = eegui_input_assset(gui_id, value, T.name);
	
	if isinstance(T, ee_types.File):
		if pretty:
			match T.pattern:
				case "*.png":
					ee_sprites.SpritePreview.draw(value);
		value = eegui_input_file(gui_id, value, T.pattern);
	
	if isinstance(T, ee_types.Flags):
		value = eegui_input_flags(gui_id, value, T.values);
	if isinstance(T, ee_types.Enum):
		value = eegui_input_enum(gui_id, value, T.values);
	if isinstance(T, ee_types.Any):
		value = eegui_input_any(gui_id, value);
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

def imgui_aabb_xywh(imgui_id, aabb):
	x0, y0, x1, y1 = aabb;
	w, h = x1-x0, y1-y0;
	x0, y0 = imgui.input_int2(f"X Y##{imgui_id}", [int(x0), int(y0)])[1];
	w, h = imgui.input_int2(f"W H##{imgui_id}", [int(w), int(h)])[1];
	return x0, y0, x0+w, y0+h;

def imgui_aabb_xyxy(imgui_id, aabb):
	x0, y0, x1, y1 = aabb;
	x0, y0 = imgui.input_int2(f"X0 Y0##{imgui_id}", [int(x0), int(y0)])[1];
	x1, y1 = imgui.input_int2(f"X1 Y1##{imgui_id}", [int(x1), int(y1)])[1];
	return x0, y0, x1, y1;

def imgui_selector(imgui_id, candidates, value, name_f = lambda x: x):
	if imgui.begin_combo(f"##{imgui_id}", str(name_f(value))):
		for candidate in candidates:
			selected = candidate == value;
			if imgui.selectable(str(name_f(candidate)), selected)[0]:
				value = candidate;
			if selected:
				imgui.set_item_default_focus();
		imgui.end_combo();
	return value;

def imgui_asset_selector(imgui_id, asset_type, asset):
	return imgui_selector(
		imgui_id,
		AssetManager.get_assets(asset_type), asset,
		lambda x: x["name"] if x != None else "None"
	);

def imgui_asset_name_selector(imgui_id, asset_type, name):
	return imgui_selector(
		imgui_id,
		["None" if x == None else (x["name"] if "name" in x else id(x)) for x in AssetManager.get_assets(asset_type)],
		name
	);

def imgui_enum_selector(imgui_id, enum_type, value):
	if isinstance(enum_type, Enum):
		enum_type = [x for x in enum_type];
	return imgui_selector(
		imgui_id,
		enum_type, value,
		lambda x: x.name
	);

def imgui_path_input(imgui_id, value, glob):
	_, result = imgui.input_text(f"##{imgui_id}", str(value));
	imgui.same_line();
	fexp = ToolWindowRegistry.lookup(FileExplorer);
	if imgui.button(f"...##{imgui_id}") and not fexp.is_open():
		fexp.open();
		fexp.get().configure(imgui_id, ee_context.env["game_path"], glob);
	if fexp.is_open() and fexp.get().is_targeting(imgui_id):
		harvest = fexp.get_result();
		result = harvest if harvest != None else result;
	return result;

def imgui_asset_input(imgui_id, type, value):
	_, result = imgui.input_text(f"##{imgui_id}", str(value));

	imgui.same_line();
	explorer = ToolWindowRegistry.lookup(AssetExplorer);
	if imgui.button(f"...##{imgui_id}") and not explorer.is_open():
		explorer.open();
		explorer.get().configure(value, type);
	if explorer.is_open() and explorer.get().is_targeting(value):
		harvest = explorer.get_result();
		result = harvest if harvest != None else result;
	
	return result;

def imgui_begin_column(imgui_id, w=None):
	if w == None:
		w = imgui.get_content_region_avail().x;
	imgui.begin_child(
		str(imgui_id),
		imgui.ImVec2(w, imgui.get_window_height()),
		0, 0
	);
def imgui_end_column():
	imgui.end_child();
	imgui.same_line();

def imgui_typed_input(imgui_id, type: ee_types.Type, value):
	return;
	