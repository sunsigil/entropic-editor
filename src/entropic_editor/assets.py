from pathlib import Path;
import json;
import asset_types;
import copy;

#########################################################
## DOCUMENT MODEL

class AssetDocument:
	def is_file_asset_document(path):
		path = Path(path);
		file = open(path, "r");
		data = json.load(file);
		file.close();

		if not isinstance(data, dict):
			return False;
		type_name = next(k for k in data.keys());
		if not isinstance(data[type_name], dict):
			return False;
		if not "type" in data[type_name]:
			return False;
		if not "instances" in data:
			return False;
		return True;
	
	def __init__(self, path):
		self.path = Path(path);
		self.directory = self.path.parent;
		file = open(path, "r");
		self.data = json.load(file);
		file.close();
		
		keys = self.data.keys();
		self.type_name = next(k for k in keys if k != "instances");
		self.type_tree = asset_types.construct_element(self.type_name, self.data[self.type_name]);
		self.type_helper = asset_types.TypeHelper(self.type_tree);
		self.instances = self.data["instances"];
	
		self.id_set = set();
		if self.type_tree.search("id") != None:
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
		new = copy.deepcopy(source) if source != None else self.type_tree.prototype();

		new["name"] = f"new_{self.type_name}";
		if "id" in new:
			new["id"] = self.take_free_id();

		self.instances.append(new);
		return new;
	
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
	document_map = {};
	documents = [];

	def load_document(path):
		try:
			document = AssetDocument(path);
			AssetManager.documents.append(document);
			AssetManager.document_map[document.type_name] = document;
			print(f"[AssetManager] Loaded {path}");
		except Exception as e:
			print(f"[AssetManager] Failed to load {path}!\n\t({e})");
			raise(e);			

	def get_document(asset_type) -> AssetDocument:
		if asset_type not in AssetManager.document_map:
			return None;
		return AssetManager.document_map[asset_type];

	def get_tree(asset_type) -> asset_types.Element:
		if asset_type not in AssetManager.document_map:
			return None;
		return AssetManager.document_map[asset_type].type_tree;

	def get_all(asset_type):
		if asset_type not in AssetManager.document_map:
			return None;
		return AssetManager.document_map[asset_type].instances;

	def get_first(asset_type):
		assets = AssetManager.get_all(asset_type);
		if assets == None or len(assets) == 0:
			return None;
		return assets[0];

	def search(asset_type, asset_name):
		return next((x for x in AssetManager.get_all(asset_type) if x["name"] == asset_name), None);

	

	