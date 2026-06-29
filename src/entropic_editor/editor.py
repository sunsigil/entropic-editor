#!/usr/bin/env python3

from pathlib import Path;
from PIL import Image;
from stat import *;
import sys;
import argparse;

import glfw;
from imgui_bundle import imgui;
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer;

import entropic_editor.ee_context as ee_context;
from entropic_editor.ee_cowtools import *;
from entropic_editor.ee_assets import *;
from entropic_editor.ee_tool_window import ToolWindow, ToolWindowRegistry;

from entropic_editor.ee_scene_editor import SceneEditor;
from entropic_editor.ee_sprites import SpriteBank;
from entropic_editor.ee_input import InputManager;
from entropic_editor.ee_prototype_editor import PrototypeEditor;
from entropic_editor.ee_dialogue_editor import DialogueGraph, DialogueEditor;
from entropic_editor.ee_recipe_editor import RecipeEditor;
from entropic_editor.ee_qr_encoder import EnDeCoder;
from entropic_editor.ee_file_explorer import FileExplorer;
from entropic_editor.ee_mesh2d_editor import Mesh2DEditor;
from entropic_editor.ee_document_editor import DocumentEditor;
from entropic_editor.ee_palette_viewer import PaletteViewer;
from entropic_editor.ee_asset_explorer import AssetExplorer;
from entropic_editor.ee_glyph_explorer import GlyphExplorer;

#from ee_theme_editor import ThemeEditor;
#from ee_anim_viewer import AnimationViewer;
#from ee_notice_editor import NoticeEditor;
#from ee_output_understander import OutputUnderstander;

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		prog="editor.py",
		description="Interactive editor for game content"
	);
	parser.add_argument("game_path", type=Path);
	parser.add_argument("--types", type=Path);
	args = parser.parse_args(sys.argv[1:]);

	editor_path = Path(__file__).parent.absolute();
	game_path = args.game_path;
	typefile_path = args.types;

	ee_context.set(ee_context.Context(game_path, "Entropic Editor", 1920, 1080));
	InputManager.initialize(ee_context.get().glfw_handle, ee_context.get().imgui_impl);

	if typefile_path != None and typefile_path.is_file():
		load_typefile(typefile_path);

	for path in (game_path/"assets").rglob("*.json"):
		if AssetDocument.is_file_asset_document(path):
			AssetManager.load_document(path);

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

	splash_img = Image.open(editor_path/"splash.png");
	splash_tex = make_texture(splash_img.tobytes(), splash_img.width, splash_img.height);
	splash_flag_list = [
		imgui.WindowFlags_.no_scrollbar,
		imgui.WindowFlags_.no_scroll_with_mouse
	];
	splash_flags = foldl(lambda a, b : a | b, 0, splash_flag_list);

	tool_flags = [
		imgui.WindowFlags_.no_saved_settings,
		imgui.WindowFlags_.no_collapse,
	];

	ToolWindowRegistry.register(ToolWindow(FileExplorer, "File Explorer", flags=tool_flags, hidden=True));
	ToolWindowRegistry.register(ToolWindow(AssetExplorer, "Asset Explorer", flags=tool_flags, hidden=True));

	ToolWindowRegistry.register(ToolWindow(PrototypeEditor, "Prototype Editor", size=(1280, 720), flags=tool_flags+[imgui.WindowFlags_.menu_bar]));
	ToolWindowRegistry.register(ToolWindow(SceneEditor, "Scene Editor", size=(1500, 880), flags=tool_flags+[imgui.WindowFlags_.menu_bar]));
	ToolWindowRegistry.register(ToolWindow(DialogueEditor, "Dialogue Editor", size=(1000, 600), flags=tool_flags));
	ToolWindowRegistry.register(ToolWindow(DialogueGraph, "Dialogue Graph", size=(1280, 720), flags=tool_flags));
	ToolWindowRegistry.register(ToolWindow(RecipeEditor, "Recipe Editor", flags=tool_flags));
	ToolWindowRegistry.register(ToolWindow(Mesh2DEditor, "Mesh2D Editor", flags=tool_flags));
	ToolWindowRegistry.register(ToolWindow(PaletteViewer, "Palette Viewer", flags=tool_flags));
	ToolWindowRegistry.register(ToolWindow(EnDeCoder, "EnDeCoder", flags=tool_flags));
	ToolWindowRegistry.register(ToolWindow(GlyphExplorer, "Glyph Explorer", flags=tool_flags));

	while ee_context.get().is_alive():
		ee_context.get().begin_frame();
		
		SpriteBank.update();
		InputManager.update();

		for document in AssetManager.documents:
			document.refresh();

		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_S):
			print(f"Saving...");
			for document in AssetManager.documents:
				document.save();

		imgui.set_next_window_pos((0, 0));
		imgui.begin(ee_context.get().name, flags=window_flags | (splash_flags if DocumentEditor.active_document == None else 0));

		if imgui.begin_main_menu_bar():

			if imgui.begin_menu("File"):
				if imgui.begin_menu("Open"):
					for document in AssetManager.documents:
						if imgui.menu_item(str(document.path.relative_to(ee_context.get().directory)), "", document == DocumentEditor.active_document)[1]:
							if DocumentEditor.active_document != None:
								DocumentEditor.active_document.save();
							DocumentEditor.active_document = document;
					imgui.end_menu();
				
				if imgui.menu_item_simple("Save all"):
					print("Saving...");
					for document in AssetManager.documents:
						document.save();
				
				if imgui.menu_item_simple("Close", enabled=DocumentEditor.active_document != None):
					DocumentEditor.active_document = None;	
				imgui.end_menu();
			
			if imgui.begin_menu("Tools"):
				for tool in ToolWindowRegistry.all():
					if not tool.hidden and imgui.menu_item_simple(tool.title):
						tool.open();
				imgui.end_menu();
			
			imgui.end_main_menu_bar();
		
		if DocumentEditor.active_document == None:
			imgui.set_scroll_x(0);
			imgui.set_scroll_y(0);
			imgui.image(imgui.ImTextureRef(splash_tex), imgui.ImVec2(splash_img.width, splash_img.height));
		else:
			DocumentEditor.draw();
		
		for tool in ToolWindowRegistry.all():
			tool.draw();
		
		imgui.end();

		ee_context.get().end_frame();

