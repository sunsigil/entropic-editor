from imgui_bundle import imgui;
from assets import AssetDocument, AssetManager, make_namespace;
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
		
		# A search flattens the tree; otherwise instances group by dotted name
		if len(self.search_cache) > 0:
			for instance in self.search_cache:
				self.draw_instance(instance, instance["name"]);
		else:
			self.draw_group(make_namespace(self.document.instances), "");

		self.rename.draw();

	def draw_instance(self, instance, label):
		gui_id = f"{label}####{id(instance)}";
		gui.typed_input(
			gui_id,
			self.document.type_tree, instance,
			previews=True, tooltip=self.show_typetip
		);
		if gui.ContextMenu.begin(gui_id):
			if imgui.menu_item_simple("Rename"):
				self.rename.begin(instance);
			if imgui.menu_item_simple("Delete"):
				self.document.delete_entry(instance);
			if imgui.menu_item_simple("Duplicate"):
				self.document.spawn_entry(instance);
			imgui.end_popup();

	def draw_group(self, node, prefix):
		for name, child in node.children.items():
			path = f"{prefix}{name}";
			if len(child.children) == 0:
				self.draw_instance(child.asset, name);
				continue;

			gui_id = f"{name}####group-{path}";
			node_open = imgui.tree_node(gui_id);
			gui.ContextMenu.ping(gui_id);
			if gui.ContextMenu.begin(gui_id):
				if imgui.menu_item_simple("New"):
					self.document.spawn_entry(name=f"{path}.new_{self.document.type_name}");
				imgui.end_popup();
			if node_open:
				if child.asset != None:
					self.draw_instance(child.asset, name);
				self.draw_group(child, f"{path}.");
				imgui.tree_pop();
