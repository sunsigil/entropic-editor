from imgui_bundle import imgui;
from assets import AssetDocument;
import types as types;
import editor_gui as gui;

class DocumentEditor:
	active_document: AssetDocument = None;

	show_typetip = False;

	search_term = "";
	search_cache = [];

	def draw():
		if imgui.begin_main_menu_bar():
			if imgui.begin_menu("Asset"):
				if imgui.menu_item_simple("New"):
					DocumentEditor.active_document.spawn_entry();
				imgui.end_menu();
			if imgui.begin_menu("View"):
				_, DocumentEditor.show_typetip = imgui.menu_item("Show typetip", "", DocumentEditor.show_typetip);
				imgui.end_menu();
			imgui.end_main_menu_bar();

		search_refresh, DocumentEditor.search_term = imgui.input_text("Search", DocumentEditor.search_term);
		if search_refresh:
			DocumentEditor.search_term = DocumentEditor.search_term.strip();
			DocumentEditor.search_cache = [];
			for instance in DocumentEditor.active_document.instances:
				if "name" in instance and DocumentEditor.search_term in instance["name"]:
					DocumentEditor.search_cache.append(instance);
		
		working_list = DocumentEditor.search_cache if len(DocumentEditor.search_cache) > 0 else DocumentEditor.active_document.instances;
		for instance in working_list:
			gui_id = f"{instance["name"]}####{id(instance)}" if "name" in instance else id(instance);
			gui.typed_input(
				gui_id,
				DocumentEditor.active_document.type_tree.T, instance,
				previews=True, tooltip=DocumentEditor.show_typetip
			);
			if gui.ContextMenu.begin(gui_id):
				if imgui.menu_item_simple("Delete"):
					DocumentEditor.active_document.delete_entry(instance);
				imgui.end_popup();