from imgui_bundle import imgui;
from assets import AssetDocument, AssetManager;
import types as types;
import editor_gui as gui;

class DocumentEditor:
	def __init__(self, document):
		self.document = document;
		self.open = True;
		self.size = imgui.ImVec2(1280, 720);

		self.show_typetip = False;

		self.search_term = "";
		self.search_cache = [];
		self.search_generation = document.generation;

		self.rename_target = None;
		self.rename_buffer = "";
		self.rename_pending = False;

	def close(self):
		self.open = False;

	def begin_rename(self, instance):
		self.rename_target = instance;
		self.rename_buffer = instance["name"];
		# Popup IDs hash against the ID stack, so the popup must be opened
		# from window level rather than from inside the context menu.
		self.rename_pending = True;
	
	def draw_rename_modal(self):
		modal_id = "Rename asset";
		if self.rename_pending:
			imgui.open_popup(modal_id);
			self.rename_pending = False;

		if self.rename_target == None:
			return;

		visible, _ = imgui.begin_popup_modal(modal_id, None, imgui.WindowFlags_.always_auto_resize);
		if not visible:
			self.rename_target = None;
			return;

		old_name = self.rename_target["name"];

		if imgui.is_window_appearing():
			imgui.set_keyboard_focus_here();
		imgui.set_next_item_width(256);
		submitted, self.rename_buffer = imgui.input_text(
			"##rename", self.rename_buffer, imgui.InputTextFlags_.enter_returns_true
		);

		new_name = self.rename_buffer.strip();
		collision = new_name != old_name and AssetManager.search(self.document.type_name, new_name) != None;
		valid = len(new_name) > 0 and not collision;

		if collision:
			imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "Name already in use");
		elif len(new_name) == 0:
			imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "Name cannot be empty");

		imgui.begin_disabled(not valid);
		commit = imgui.button("Rename") or (submitted and valid);
		imgui.end_disabled();
		imgui.same_line();
		cancel = imgui.button("Cancel") or imgui.is_key_pressed(imgui.Key.escape);

		if commit:
			if new_name != old_name:
				AssetManager.rename(self.document.type_name, old_name, new_name);
			self.rename_target = None;
			imgui.close_current_popup();
		elif cancel:
			self.rename_target = None;
			imgui.close_current_popup();

		imgui.end_popup();

	def draw(self):
		imgui.set_next_window_size(self.size);
		_, self.open = imgui.begin(self.document.type_name, self.open, flags=imgui.WindowFlags_.menu_bar);

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
					self.begin_rename(instance);
				if imgui.menu_item_simple("Delete"):
					self.document.delete_entry(instance);
				if imgui.menu_item_simple("Duplicate"):
					self.document.spawn_entry(instance);
				imgui.end_popup();

		self.draw_rename_modal();

		self.size = imgui.get_window_size();
		imgui.end();
