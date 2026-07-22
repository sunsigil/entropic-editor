from imgui_bundle import imgui;
from assets import AssetDocument, AssetManager;
import types as types;
import editor_gui as gui;
import input;
import glfw;

class DocumentEditor:
	def __init__(self, document):
		self.document = document;
		self.open = True;
		self.size = imgui.ImVec2(1280, 720);

		self.show_typetip = False;

		self.search_term = "";
		self.search_cache = [];

		self.rename_from = "";
		self.rename_to = "";

	def draw(self):
		imgui.set_next_window_size(self.size);
		_, self.open = imgui.begin(self.document.type_name, self.open);

		if imgui.begin_menu_bar():
			if imgui.begin_menu("Asset"):
				if imgui.menu_item_simple("New"):
					self.document.spawn_entry();
				if imgui.begin_menu("Rename"):
					imgui.set_next_item_width(128);
					_, self.rename_from = imgui.input_text("From", self.rename_from);
					imgui.set_next_item_width(128);
					_, self.rename_to = imgui.input_text("To", self.rename_to);
					if imgui.button("Commit"):
						AssetManager.rename(self.document.type_name, self.rename_from, self.rename_to);
						self.rename_from = "";
						self.rename_to = "";
					imgui.end_menu();
				imgui.end_menu();
			
			if imgui.begin_menu("View"):
				_, self.show_typetip = imgui.menu_item("Show typetip", "", self.show_typetip);
				imgui.end_menu();
			imgui.end_menu_bar();
		
		if input.InputManager.is_command(glfw.KEY_Z):
			AssetManager.undo();

		search_refresh, self.search_term = imgui.input_text("Search", self.search_term);
		if search_refresh:
			self.search_term = self.search_term.strip();
			self.search_cache = [];
			for instance in self.document.instances:
				if "name" in instance and self.search_term in instance["name"]:
					self.search_cache.append(instance);
		
		working_list = self.search_cache if len(self.search_cache) > 0 else self.document.instances;
		for instance in working_list:
			gui_id = f"{instance["name"]}####{id(instance)}" if "name" in instance else id(instance);
			gui.typed_input(
				gui_id,
				self.document.type_tree, instance,
				previews=True, tooltip=self.show_typetip
			);
			if gui.ContextMenu.begin(gui_id):
				if imgui.menu_item_simple("Delete"):
					self.document.delete_entry(instance);
				if imgui.menu_item_simple("Duplicate"):
					self.document.spawn_entry(instance);
				imgui.end_popup();

		self.size = imgui.get_window_size();
		imgui.end();
		