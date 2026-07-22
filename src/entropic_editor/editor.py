#!/usr/bin/env python3

from pathlib import Path;
from PIL import Image;
from stat import *;
import sys;
import argparse;

import glfw;
from imgui_bundle import imgui;
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer;
import context;

from cowtools import *;
from assets import *;
from tool_window import Tool, ToolWindowRegistry;
import asset_types;

from scenes.scene_editor import SceneEditor;
from sprites import SpriteBank;
from input import InputManager;
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
	
	context.set(context.Context(
		editor_path, game_path,
		"Entropic Editor", 1920, 1080)
	);

	InputManager.initialize(context.get().glfw_handle, context.get().imgui_impl);
	def window_close_callback(handle):
		for tool in ToolWindowRegistry.all():
			if tool.is_open():
				tool.close();
				glfw.set_window_should_close(handle, False);
				return;
		glfw.set_window_should_close(handle, True);
	glfw.set_window_close_callback(context.get().glfw_handle, window_close_callback);

	if typefile_path != None and typefile_path.is_file():
			asset_types.load_typefile(typefile_path);
	for path in (game_path/"assets").rglob("*.json"):
		if AssetDocument.is_file_asset_document(path):
			AssetManager.load_document(path);
	make_backups(game_path/"backups/cold", cold=True);

	document_editors = [];
	
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

	splash_img = Image.open(editor_path/"resources/splash.png");
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

	ToolWindowRegistry.register(Tool(FileExplorer, "File Explorer", flags=tool_flags+[imgui.WindowFlags_.menu_bar], hidden=True));
	ToolWindowRegistry.register(Tool(AssetExplorer, "Asset Explorer", flags=tool_flags, hidden=True));
	ToolWindowRegistry.register(Tool(TextEditor, "Script Editor", flags=tool_flags, hidden=True, singleton=False));

	ToolWindowRegistry.register(Tool(PrototypeEditor, "Prototype Editor", size=(1280, 720), flags=tool_flags+[imgui.WindowFlags_.menu_bar]));
	ToolWindowRegistry.register(Tool(SceneEditor, "Scene Editor", size=(1500, 880), flags=tool_flags+[imgui.WindowFlags_.menu_bar]));
	ToolWindowRegistry.register(Tool(DialogueEditor, "Dialogue Editor", size=(1280, 720), flags=tool_flags+[imgui.WindowFlags_.menu_bar]));
	ToolWindowRegistry.register(Tool(RecipeEditor, "Recipe Editor", flags=tool_flags));
	ToolWindowRegistry.register(Tool(Mesh2DEditor, "Mesh2D Editor", flags=tool_flags));
	ToolWindowRegistry.register(Tool(PaletteViewer, "Palette Viewer", flags=tool_flags));
	ToolWindowRegistry.register(Tool(EnDeCoder, "EnDeCoder", flags=tool_flags));
	ToolWindowRegistry.register(Tool(GlyphExplorer, "Glyph Explorer", flags=tool_flags));
	ToolWindowRegistry.register(Tool(SpriteImporter, "Sprite Importer", flags=tool_flags));

	while context.get().is_alive():
		context.get().begin_frame();

		SpriteBank.refresh();
		InputManager.tick();

		for document in AssetManager.documents:
			document.refresh();
		make_backups(game_path/"backups/hot");
		if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_S):
			for document in AssetManager.documents:
				document.save();

		de_trash = [de for de in document_editors if not de.open];
		for de in de_trash:
			document_editors.remove(de);
		def doc_is_open(doc):
			return next((x for x in document_editors if x.document.type_name == doc.type_name), None) != None;

		imgui.set_next_window_pos((0, 0));
		imgui.set_next_window_size(imgui.ImVec2(1920*0.8, 1080*0.8));
		imgui.begin(context.get().name, flags=window_flags | splash_flags);

		if imgui.begin_main_menu_bar():
			if imgui.begin_menu("File"):
				if imgui.begin_menu("Open"):
					for document in AssetManager.documents:
						if imgui.menu_item(document.type_name, "", doc_is_open(document))[1]:
							if not doc_is_open(document):
								document_editors.append(DocumentEditor(document));
					imgui.end_menu();
				
				if imgui.menu_item_simple("Save all"):
					print("Saving...");
					for document in AssetManager.documents:
						document.save();
				imgui.end_menu();
			
			if imgui.begin_menu("Tools"):
				for tool in ToolWindowRegistry.all():
					if not tool.hidden and imgui.menu_item_simple(tool.title):
						tool.open();
				imgui.end_menu();
			imgui.end_main_menu_bar();

			imgui.set_scroll_x(0);
			imgui.set_scroll_y(0);
			imgui.image(imgui.ImTextureRef(splash_tex), imgui.ImVec2(splash_img.width, splash_img.height));
		imgui.end();

		for de in document_editors:
			de.draw();
		for tool in ToolWindowRegistry.all():
			tool.draw();
		imgui.show_id_stack_tool_window();

		context.get().end_frame();

