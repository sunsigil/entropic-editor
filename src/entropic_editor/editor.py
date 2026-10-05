#!/usr/bin/env python3

# PyOpenGL has to bind its GL/EGL entry points before imgui_bundle loads the
# GLFW it ships with, or the two end up holding separate library instances: the
# context GLFW makes is then invisible to PyOpenGL, GetCurrentContext() returns
# 0, and the first call that stores per-context state (glVertexAttribPointer,
# from imgui's backend) dies with "Attempt to retrieve context when no valid
# context". Keep this above every other import.
import OpenGL.GL;

from pathlib import Path;
from PIL import Image;
from stat import *;
import sys;
import argparse;
import traceback;

import glfw;
from imgui_bundle import imgui;
from rendering.images import Texture;
import window;
import paths;

from cowtools import *;
from assets import *;
from panels import Tool, ToolRegistry, PanelManager;
import asset_types;

from sprites import SpriteBank;
from scripts import ScriptBank;
from input import InputManager;

from scenes.scene_editor import SceneEditor;
from scenes.prototype_editor import PrototypeEditor;
from dialogue_editor import DialogueEditor;
from recipe_editor import RecipeEditor;
from coder import EnDeCoder;
from file_explorer import FileExplorer;
from mesh_editor import Mesh2DEditor;
from document_editor import DocumentEditor;
from palette_viewer import PaletteViewer;
from asset_explorer import AssetExplorer;
from glyph_viewer import GlyphExplorer;
from text_editor import TextEditor;

from sprites import SpriteImporter;

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		prog="editor.py",
		description="Interactive editor for game content"
	);
	parser.add_argument("game_path", type=Path);
	parser.add_argument("--types", type=Path);
	args = parser.parse_args(sys.argv[1:]);

	editor_path = Path(__file__).parent.absolute();
	game_path = Path(args.game_path).absolute();
	typefile_path = args.types;
	
	paths.configure(editor_path, game_path);
	win = window.Window("Entropic Editor", 1920, 1080);

	if typefile_path != None and typefile_path.is_file():
		asset_types.load_typefile(typefile_path);
	
	for path in (game_path/"assets").rglob("*.json"):
		if AssetDocument.is_file_asset_document(path):
			AssetManager.load_document(path);
	make_backups(game_path/"backups/cold", cold=True);
	HOT_BACKUP_INTERVAL = 5.0;
	hot_backup_timestamp = glfw.get_time();

	
	window_flag_list = [
		imgui.WindowFlags_.no_saved_settings,
		imgui.WindowFlags_.no_move,
		imgui.WindowFlags_.no_resize,
		imgui.WindowFlags_.no_nav_inputs,
		imgui.WindowFlags_.no_nav_focus,
		imgui.WindowFlags_.no_collapse,
		imgui.WindowFlags_.no_background,
		imgui.WindowFlags_.no_bring_to_front_on_focus,
	];
	window_flags = foldl(lambda a, b : a | b, 0, window_flag_list);

	splash = Texture.load(editor_path/"resources/splash.png");
	splash_flag_list = [
		imgui.WindowFlags_.no_scrollbar,
		imgui.WindowFlags_.no_scroll_with_mouse
	];
	splash_flags = foldl(lambda a, b : a | b, 0, splash_flag_list);

	tool_flags = [
		imgui.WindowFlags_.no_saved_settings,
		imgui.WindowFlags_.no_collapse,
	];

	ToolRegistry.register(Tool(FileExplorer, "File Explorer", flags=tool_flags+[imgui.WindowFlags_.menu_bar], hidden=True, picker=True));
	ToolRegistry.register(Tool(AssetExplorer, "Asset Explorer", flags=tool_flags, hidden=True, picker=True));
	ToolRegistry.register(Tool(TextEditor, "Script Editor", flags=tool_flags, hidden=True));

	ToolRegistry.register(Tool(PrototypeEditor, "Prototype Editor", size=(1280, 720), flags=tool_flags+[imgui.WindowFlags_.menu_bar]));
	ToolRegistry.register(Tool(SceneEditor, "Scene Editor", size=(1500, 880), flags=tool_flags+[imgui.WindowFlags_.menu_bar]));
	ToolRegistry.register(Tool(DialogueEditor, "Dialogue Editor", size=(1280, 720), flags=tool_flags+[imgui.WindowFlags_.menu_bar]));
	ToolRegistry.register(Tool(RecipeEditor, "Recipe Editor", flags=tool_flags));
	ToolRegistry.register(Tool(Mesh2DEditor, "Mesh2D Editor", flags=tool_flags));
	ToolRegistry.register(Tool(PaletteViewer, "Palette Viewer", flags=tool_flags+[imgui.WindowFlags_.menu_bar]));
	ToolRegistry.register(Tool(EnDeCoder, "EnDeCoder", flags=tool_flags));
	ToolRegistry.register(Tool(GlyphExplorer, "Glyph Explorer", flags=tool_flags));
	ToolRegistry.register(Tool(SpriteImporter, "Sprite Importer", flags=tool_flags));

	InputManager.initialize(win.glfw_handle, win.imgui_impl);

	def window_close_callback(handle):
		if PanelManager.close_last_focused():
			glfw.set_window_should_close(handle, False);
		else:
			glfw.set_window_should_close(handle, True);
	glfw.set_window_close_callback(win.glfw_handle, window_close_callback);

	try:
		while win.is_alive():
			win.begin_frame();

			SpriteBank.refresh();
			ScriptBank.refresh(AssetManager.get_all("script"));
			InputManager.tick();

			for document in AssetManager.documents:
				document.refresh(changed_only=True);

			History.tick(idle=not imgui.is_any_item_active() and not imgui.is_any_mouse_down());
			if not imgui.get_io().want_text_input and InputManager.is_command(glfw.KEY_Z):
				if InputManager.is_held(glfw.KEY_LEFT_SHIFT) or InputManager.is_held(glfw.KEY_RIGHT_SHIFT):
					History.redo();
				else:
					History.undo();

			if glfw.get_time() - hot_backup_timestamp >= HOT_BACKUP_INTERVAL:
				make_backups(game_path/"backups/hot", cold=False);
				hot_backup_timestamp = glfw.get_time();
			if InputManager.is_command(glfw.KEY_S):
				for document in AssetManager.documents:
					document.save();

			imgui.set_next_window_pos((0, 0));
			imgui.set_next_window_size(imgui.ImVec2(*win.size));
			imgui.begin(win.name, flags=window_flags | splash_flags);

			if imgui.begin_main_menu_bar():
				if imgui.begin_menu("File"):
					if imgui.begin_menu("Open"):
						for document in AssetManager.documents:
							existing = PanelManager.find(DocumentEditor.key_for(document));
							clicked, _ = imgui.menu_item(document.type_name, "", existing != None);
							if clicked:
								if existing == None:
									PanelManager.open(DocumentEditor(document));
								else:
									existing.focus();
						imgui.end_menu();
					
					if imgui.menu_item_simple("Save all"):
						print("Saving...");
						for document in AssetManager.documents:
							document.save();
					imgui.end_menu();
				
				if imgui.begin_menu("Tools"):
					for tool in ToolRegistry.all():
						if not tool.hidden and imgui.menu_item_simple(tool.title):
							tool.open();
					imgui.end_menu();
				imgui.end_main_menu_bar();

				imgui.set_scroll_x(0);
				imgui.set_scroll_y(0);
				avail = imgui.get_content_region_avail();
				fit = min(avail.x / splash.width, avail.y / splash.height);
				fitted = imgui.ImVec2(splash.width * fit, splash.height * fit);
				cursor = imgui.get_cursor_pos();
				imgui.set_cursor_pos(imgui.ImVec2(cursor.x + (avail.x - fitted.x) / 2, cursor.y + (avail.y - fitted.y) / 2));
				imgui.image(imgui.ImTextureRef(splash.handle), fitted);
			imgui.end();

			PanelManager.draw_all();

			win.end_frame();
	except Exception:
		traceback.print_exc();
		recovery_dir = game_path/"backups/recovery";
		try:
			make_backups(recovery_dir, cold=False);
			print(f"[Editor] Crashed. Unsaved work written to {recovery_dir}");
		except Exception:
			print("[Editor] Crashed, and the recovery save also failed:");
			traceback.print_exc();
		raise;
	finally:
		win.shutdown();
