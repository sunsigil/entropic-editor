from pathlib import Path;
from imgui_bundle import imgui;
import os;
from assets import AssetManager;
import copy;

class FileExplorer:
	last = None;

	def __init__(self):
		self.anchor = None;
		self.glob = None;
		self.current = None;

		self.search = "";
		self.asset_type = None;
		self.filter_unused = False;

		self.new_file_name = "";
	
		self.result = None;
	
	def configure(self, anchor, glob, asset_type=None, return_absolute=False):
		refresh = FileExplorer.last == None or anchor != FileExplorer.last.anchor;

		self.anchor = Path(anchor);
		self.glob = glob;
		self.asset_type = asset_type;
		self.return_absolute = return_absolute;

		if refresh:
			self.current = self.anchor;
			self.search = "";
			self.filter_unused = False;
		else:
			self.current = FileExplorer.last.current;
			self.search = FileExplorer.last.search;
			self.filter_unused = FileExplorer.last.filter_unused;
	
	def __del__(self):
		FileExplorer.last = copy.copy(self);
	
	def draw(self):
		if imgui.begin_menu_bar():
			if imgui.begin_menu("File"):
				if imgui.begin_menu("New"):
					imgui.set_next_item_width(128);
					_, self.new_file_name = imgui.input_text("Name", self.new_file_name);
					imgui.same_line();
					if imgui.button("Add"):
						Path(Path(self.current)/self.new_file_name).touch();
					imgui.end_menu();
				imgui.end_menu();
			imgui.end_menu_bar();

		listings = [self.current.parent.absolute()];
		for entry in self.current.iterdir():
			hidden = entry.name.startswith(".") or entry.name.startswith("__");
			if entry.absolute().is_dir() and not hidden:
				listings.append(entry);
		for entry in self.current.glob(self.glob):
			if not entry in listings:
				listings.append(entry);
		
		_, self.search = imgui.input_text("Search", self.search);
		if len(self.search) > 0:
			listings = list(filter(lambda x: self.search in str(x.name), listings));
		
		if self.asset_type != None:
			assets = AssetManager.get_all(self.asset_type);
			if len(assets) > 0 and "path" in assets[0]:
				_, self.filter_unused = imgui.checkbox("Unused", self.filter_unused);
				if self.filter_unused:
					paths = [x["path"] for x in assets];
					unused = [x for x in listings if not str(Path(os.path.relpath(x.absolute(), self.anchor.absolute()))) in paths];
					listings = unused;

		listings.sort();
		
		for item in listings:
			name = ".." if item == self.current.parent.absolute() else item.name;
			name = f"{name}/" if item.is_dir() else name;
			if imgui.menu_item_simple(name):
				if item.is_dir():
					self.current = item;
					self.search = "";
				else:
					self.result = Path(os.path.relpath(item.absolute(), self.anchor.absolute()));
	
		if self.result != None:
			self.result = (self.current/self.result).absolute();

	def should_close(self):
		return self.result != None;
		
	def get_result(self):
		return self.result;