from imgui_bundle import imgui;
from assets import AssetDocument, AssetManager;
import editor_gui as gui;
from panels import Panel;

class DocumentEditor(Panel):
	def key_for(document):
		return (DocumentEditor, document.type_name);

	def __init__(self, document):
		super().__init__(document.type_name, size=(1280, 720), flags=imgui.WindowFlags_.menu_bar, key=DocumentEditor.key_for(document));
		self.document = document;

		self.show_typetip = False;

		self.search_term = "";
		self.search_cache = [];
		self.search_generation = document.generation;

		self.rename = gui.RenameModal.for_assets(document.type_name);

	def body(self):

		if imgui.begin_menu_bar():
			if imgui.begin_menu("Asset"):
				if imgui.menu_item_simple("New"):
					self.document.spawn_entry();
				imgui.end_menu();
			
			if imgui.begin_menu("View"):
				_, self.show_typetip = imgui.menu_item("Show typetip", "", self.show_typetip);
				imgui.end_menu();
			imgui.end_menu_bar();
		
		search_refresh, self.search_term = imgui.input_text("Search", self.search_term);
		# Undo may add or remove instances, so the cached search results must be rebuilt.
		if search_refresh or self.search_generation != self.document.generation:
			self.search_generation = self.document.generation;
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
				if "name" in instance and imgui.menu_item_simple("Rename"):
					self.rename.begin(instance);
				if imgui.menu_item_simple("Delete"):
					self.document.delete_entry(instance);
				if imgui.menu_item_simple("Duplicate"):
					self.document.spawn_entry(instance);
				imgui.end_popup();

		self.rename.draw();
