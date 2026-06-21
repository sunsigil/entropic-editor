from pathlib import Path;
import json;
import ee_types;
import copy;

#########################################################
## DOCUMENT MODEL

class AssetDocument:
	def __init__(self, path):
		self.path = Path(path);
		self.directory = self.path.parent;
		file = open(path, "r");
		self.data = json.load(file);
		file.close();
		
		keys = self.data.keys();
		self.type_name = next(k for k in keys if k != "instances");
		self.type_helper = ee_types.TypeHelper(self.type_name, self.data[self.type_name]);
		self.instances = self.data["instances"];
	
		self.id_set = set();
		if self.type_helper.search("id") != None:
			for entry in self.instances:
				self.id_set.add(entry["id"]);
	
		self.refresh();
	
	def take_free_id(self):
		M = max(self.id_set) if len(self.id_set) > 0 else 0;
		i = 0;
		while i <= M:
			if not i in self.id_set:
				self.id_set.add(i);
				return i;
			i += 1;
		self.id_set.add(M+1);
		return M+1;
	
	def spawn_entry(self, source=None):
		new = self.type_helper.abstract_tree.prototype();

		new["name"] = f"new_{self.type_name}";
		if "id" in new:
			new["id"] = self.take_free_id();
		
		if source != None:
			for k,v in source.items():
				new[k] = copy.deepcopy(v);

		self.instances.append(new);
	
	def duplicate_entry(self, entry):
		new = copy.deepcopy(entry);
		if "id" in new:
			new["id"] = self.take_free_id();
		self.instances.append(new);
	
	def delete_entry(self, entry):
		if "id" in entry:
			self.id_set.remove(entry["id"]);
		self.instances.remove(entry);
	
	def refresh(self):
		for i in range(len(self.instances)):
			self.type_helper.rectify(self.instances[i]);
	
	def save(self):
		if self.type_name in self.data and "instances" in self.data:
			file = open(self.path, "w");
			file.seek(0);
			file.truncate();
			file.write(json.dumps(self.data, indent=4));
			file.close();

class AssetManager:
	directories = [];
	documents = [];
	active_document = None;

	def initialize(directories):
		AssetManager.directories = [Path(d) for d in directories];
		AssetManager.documents = [];

		for directory in AssetManager.directories:
			for filepath in directory.iterdir():
				ext = filepath.suffix;
				if ext == ".json":
					safe = False;
					if safe:
						try:
							document = AssetDocument(filepath);
							AssetManager.documents.append(document);
							print(f"[AssetManager] Loaded {filepath}");
						except Exception as e:
							print(f"[AssetManager] Failed to load {filepath}!\n\t({e})");
					else:
						document = AssetDocument(filepath);
						AssetManager.documents.append(document);
						print(f"[AssetManager] Loaded {filepath}");
	def types():
		return [document.type_name for document in AssetManager.documents];

	def has_type(name):
		return name in [document.type_name for document in AssetManager.documents];

	def get_document(name) -> AssetDocument:
		return next((document for document in AssetManager.documents if document.type_name == name), None);

	def get_assets(asset_type):
		return next((document.instances for document in AssetManager.documents if document.type_name == asset_type), None);

	def search(asset_type, asset_name):
		return next((asset for asset in AssetManager.get_assets(asset_type) if asset["name"] == asset_name), None);

	def get_first(asset_type):
		assets = AssetManager.get_assets(asset_type);
		if assets == None or len(assets) == 0:
			return None;
		return assets[0];

	