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
	