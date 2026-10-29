from imgui_bundle import imgui;
from pathlib import Path;
import math;

from assets import AssetManager, make_namespace;
from input import InputManager;
import project;
import sprites;

#########################################################
## SOURCES

class Source:
	def key(self):
		raise NotImplementedError();
	def root(self):
		raise NotImplementedError();
	def children(self, container):
		raise NotImplementedError();
	def is_container(self, entry):
		raise NotImplementedError();
	def has_value(self, entry):
		raise NotImplementedError();
	def label(self, entry):
		raise NotImplementedError();
	def value(self, entry):
		raise NotImplementedError();
	def thumbnail(self, entry):
		return None;
	def filters(self):
		return [];
	def create(self, container, name):
		return False;

class FileSource(Source):
	def __init__(self, anchor, glob, asset_type=None):
		self.anchor = Path(anchor);
		self.glob = glob;
		self.asset_type = asset_type;

	def key(self):
		return ("file", self.anchor);
	def root(self):
		return self.anchor;
	def children(self, directory):
		entries = [];
		for entry in directory.iterdir():
			hidden = entry.name.startswith(".") or entry.name.startswith("__");
			if entry.is_dir() and not hidden:
				entries.append(entry);
		for entry in directory.glob(self.glob):
			if not entry in entries:
				entries.append(entry);
		return sorted(entries);
	def is_container(self, entry):
		return entry.is_dir();
	def has_value(self, entry):
		return not entry.is_dir();
	def label(self, entry):
		return entry.name;
	def value(self, entry):
		return project.relativize(entry);
	def filters(self):
		if self.asset_type != "sprite":
			return [];
		return [("Unused", lambda entry: not sprites.SpriteBank.is_image_used(entry.absolute()))];
	def create(self, directory, name):
		(directory/name).touch();
		return True;

class DocumentSource(Source):
	def __init__(self, asset_type):
		self.asset_type = asset_type;
		self.document = AssetManager.get_document(asset_type);
		self.has_sprites = asset_type == "sprite" or "sprite" in self.document.type_tree.elements;

	def key(self):
		return ("document", self.asset_type);
	def root(self):
		return make_namespace([x for x in self.document.instances if not self.is_anonymous(x)]);
	def is_anonymous(self, instance):
		return instance.get("anonymous", False) or instance.get("metadata", {}).get("anonymous", False);
	def children(self, node):
		return list(node.children.values());
	def is_container(self, node):
		return len(node.children) > 0;
	def has_value(self, node):
		return node.asset != None;
	def label(self, node):
		return node.name;
	def value(self, node):
		return node.asset["name"];
	def thumbnail(self, node):
		if not self.has_sprites or node.asset == None:
			return None;
		name = node.asset["name"] if self.asset_type == "sprite" else node.asset.get("sprite", "");
		return sprites.SpriteBank.search(name);

#########################################################
## EXPLORER

THUMBNAIL_SIZE = 64;

class Explorer:
	memory = {};

	def __init__(self):
		self.source = None;
		self.path = [];
		self.search = "";
		self.checked = [];
		self.new_name = "";
		self.result = None;

	def configure(self, source):
		self.source = source;
		self.path, self.search, self.checked = Explorer.memory.get(source.key(), ([], "", []));
		self.path = list(self.path);
		self.checked = list(self.checked);

	def __del__(self):
		if self.source != None:
			Explorer.memory[self.source.key()] = (self.path, self.search, self.checked);

	def current(self):
		node = self.source.root();
		for depth, label in enumerate(self.path):
			child = next((x for x in self.source.children(node) if self.source.label(x) == label), None);
			if child == None:
				del self.path[depth:];
				break;
			node = child;
		return node;

	def draw(self):
		source = self.source;
		current = self.current();

		if imgui.begin_menu_bar():
			if imgui.begin_menu("File"):
				if imgui.begin_menu("New"):
					imgui.set_next_item_width(128);
					_, self.new_name = imgui.input_text("Name", self.new_name);
					imgui.same_line();
					if imgui.button("Add"):
						source.create(current, self.new_name);
					imgui.end_menu();
				imgui.end_menu();
			imgui.end_menu_bar();

		_, self.search = imgui.input_text("Search", self.search);

		filters = source.filters();
		if len(self.checked) != len(filters):
			self.checked = [False] * len(filters);
		for i, (label, _) in enumerate(filters):
			_, self.checked[i] = imgui.checkbox(label, self.checked[i]);

		entries = source.children(current);
		if len(self.search) > 0:
			entries = [x for x in entries if self.search in source.label(x)];
		for (_, predicate), checked in zip(filters, self.checked):
			if checked:
				entries = [x for x in entries if source.is_container(x) or predicate(x)];

		grid = any(source.thumbnail(x) != None for x in entries);
		if grid:
			self.draw_grid(entries);
		else:
			self.draw_list(entries);

	def select(self, entry):
		source = self.source;
		container = source.is_container(entry);
		item = source.has_value(entry);
		if item and (not container or InputManager.is_command_held()):
			self.result = source.value(entry);
		elif container:
			self.path.append(source.label(entry));
			self.search = "";

	def draw_list(self, entries):
		source = self.source;
		if len(self.path) > 0 and imgui.menu_item_simple("../"):
			self.path.pop();
			self.search = "";
		for entry in entries:
			label = source.label(entry);
			if source.is_container(entry):
				label = f"{label}/";
			if imgui.menu_item_simple(label):
				self.select(entry);

	def draw_grid(self, entries):
		source = self.source;
		size = imgui.ImVec2(THUMBNAIL_SIZE, THUMBNAIL_SIZE);
		cols = max(1, int(imgui.get_content_region_avail().x / 1.25 // THUMBNAIL_SIZE));

		cells = [None] + entries if len(self.path) > 0 else entries;
		for i, entry in enumerate(cells):
			imgui.begin_group();
			if entry == None:
				if imgui.button("../", size):
					self.path.pop();
					self.search = "";
				imgui.text("");
			else:
				label = source.label(entry);
				sprite = source.thumbnail(entry);
				if sprite != None:
					clicked = imgui.image_button(f"##{i}", imgui.ImTextureRef(sprite.frames[0].handle), size);
				else:
					clicked = imgui.button(f"{label}/##{i}", size);
				if clicked:
					self.select(entry);
				imgui.text(label[:10]);
			imgui.end_group();
			if (i + 1) % cols != 0:
				imgui.same_line();
		imgui.new_line();
