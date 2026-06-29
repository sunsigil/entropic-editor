from pathlib import Path;
from imgui_bundle import imgui;
from entropic_editor.ee_cowtools import foldl;
import os;
from entropic_editor.ee_assets import AssetManager;
import copy;

class FileExplorer:
	last = None;

	def __init__(self):
		self.target = None;
		self.anchor = None;
		self.glob = None;
		self.current = None;

		self.search = "";
		self.asset_type = None;
		self.filter_unused = False;
	
		self.result = None;
	
	def configure(self, target, anchor, glob, asset_type=None):
		refresh = FileExplorer.last == None or anchor != FileExplorer.last.anchor;

		self.target = target;
		self.anchor = Path(anchor);
		self.glob = glob;
		self.asset_type = asset_type;

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
			assets = AssetManager.get_all("sprite");
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
	
	def is_targeting(self, target):
		return target == self.target;

	def should_close(self):
		return self.result != None;
		
	def get_result(self):
		return self.result;