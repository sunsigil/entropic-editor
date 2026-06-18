from imgui_bundle import imgui;
from ee_assets import AssetManager, AssetDocument, DocumentHelper;
from ee_sprites import SpritePreview;
import ee_types;
from ee_tool_window import ToolWindow, ToolWindowRegistry;
from ee_asset_explorer import AssetExplorer;
from ee_file_explorer import FileExplorer;
from ee_imgui import *;
import copy;

class DocumentEditor:
	show_typetip = False;

	search_term = "";
	search_cache = [];

	def draw(doc : AssetDocument):
		_, DocumentEditor.show_typetip = imgui.checkbox("Show typetip", DocumentEditor.show_typetip);

		search_refresh, DocumentEditor.search_term = imgui.input_text("Search", DocumentEditor.search_term);
		if search_refresh:
			DocumentEditor.search_term = DocumentEditor.search_term.strip();
			DocumentEditor.search_cache = [];
			for instance in doc.instances:
				if "name" in instance and DocumentEditor.search_term in instance["name"]:
					DocumentEditor.search_cache.append(instance);
		
		working_list = DocumentEditor.search_cache if len(DocumentEditor.search_cache) > 0 else doc.instances;
		for instance in working_list:
			eegui_typed_input(
				f"{instance["name"]}####{id(instance)}" if "name" in instance else id(instance),
				doc.type_helper.abstract_tree.T, instance,
				previews=True, tooltip=DocumentEditor.show_typetip
			);