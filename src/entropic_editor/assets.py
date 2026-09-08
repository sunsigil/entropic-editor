from pathlib import Path;
import json;
import asset_types;
import copy;
import shutil;

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
		
		self.type_name, type_expr = next((k,v) for (k,v) in self.data.items() if k != "instances");
		self.type_tree = asset_types.construct_type(type_expr["type"]);
		if isinstance(self.type_tree, asset_types.Object) and "name" in self.type_tree.elements:
			self.type_tree.elements["name"].read_only = True;
		self.type_helper = asset_types.TypeHelper(self.type_tree);
		self.instances = self.data["instances"];
	
		self.id_set = set();
		if self.type_tree.search("id") != None:
			for entry in self.instances:
				if not "id" in entry:
					entry["id"] = self.take_free_id();
				if entry["id"] in self.id_set:
					print(f"[{self.type_name.upper()}] ID {entry["id"]} collides with existing ID set!");
				self.id_set.add(entry["id"]);
	
		self.refresh();

		self.committed = copy.deepcopy(self.instances);
		self.generation = 0;

	def rebuild_id_set(self):
		self.id_set = set();
		if self.type_tree.search("id") != None:
			for entry in self.instances:
				if "id" in entry:
					self.id_set.add(entry["id"]);

	def on_restored(self):
		self.rebuild_id_set();
		self.generation += 1;
	
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
	
	def spawn_entry(self, source=None, name=None):
		new = copy.deepcopy(source) if source != None else self.type_tree.prototype();

		new["name"] = f"new_{self.type_name}" if name == None else name;
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
	
	def save(self, path=None):
		if path == None:
			path = self.path;
		file = open(path, "w");
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

	def get_tree(asset_type) -> asset_types.Type:
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

	def rename(asset_type, asset_name, new_name):
		asset = AssetManager.search(asset_type, asset_name);
		if asset == None:
			return;

		asset["name"] = new_name;

		for doc in AssetManager.documents:
			assets = AssetManager.get_all(doc.type_name);
			for asset in assets:
				nodes = doc.type_helper.flatten(asset);
				for node in nodes:
					if isinstance(node.T, asset_types.List) and node.T.T == asset_types.Asset(asset_type):
						for i,v in enumerate(node.I):
							if v == asset_name:
								node.I[i]= new_name;
					if isinstance(node.T, asset_types.Object):
						for key in node.children:
							child = node.children[key];
							if child.T == asset_types.Asset(asset_type) and node.I[key] == asset_name:
								node.I[key] = new_name;

#########################################################
## HISTORY

def _list_key(items):
	# Lists of dicts are matched by a stable key rather than by index, so a
	# deletion in the middle of a list doesn't shift every later element's
	# content into a different dict object on undo.
	if len(items) == 0 or not all(isinstance(x, dict) for x in items):
		return None;
	for key in ("id", "name"):
		if all(key in x for x in items):
			return key;
	return None;

def _same_kind(a, b):
	return (isinstance(a, dict) and isinstance(b, dict)) or (isinstance(a, list) and isinstance(b, list));

def restore_in_place(target, source):
	"""Make target structurally equal to source while keeping the identity of every
	container that still exists at the same place, so references held by editors
	(current scene, current prototype, tree-node state keyed on id()) stay valid.
	Nothing from source is ever inserted into target directly; new content is copied."""
	if isinstance(target, dict):
		for key in [k for k in target if k not in source]:
			del target[key];
		for key, value in source.items():
			if key in target and _same_kind(target[key], value):
				restore_in_place(target[key], value);
			else:
				target[key] = copy.deepcopy(value);

	elif isinstance(target, list):
		key = _list_key(target);
		if key != None and key == _list_key(source):
			pool = {};
			for item in target:
				pool.setdefault(item[key], []).append(item);
			rebuilt = [];
			for item in source:
				candidates = pool.get(item[key]);
				if candidates:
					match = candidates.pop(0);
					restore_in_place(match, item);
					rebuilt.append(match);
				else:
					rebuilt.append(copy.deepcopy(item));
			target[:] = rebuilt;
		else:
			n = min(len(target), len(source));
			for i in range(n):
				if _same_kind(target[i], source[i]):
					restore_in_place(target[i], source[i]);
				else:
					target[i] = copy.deepcopy(source[i]);
			del target[n:];
			target.extend(copy.deepcopy(source[n:]));

class History:
	"""Snapshot-based undo across every loaded document.

	Editors mutate document instances in place through immediate-mode widgets,
	so instead of recording operations, History periodically compares each
	document against its last committed copy and stores the old copy when it
	differs. One undo entry may span several documents (e.g. a rename)."""
	LIMIT = 64;
	IDLE_COMMIT_INTERVAL = 15; # frames

	undo_stack = [];
	redo_stack = [];
	_was_idle = True;
	_frame = 0;

	def commit():
		entry = [];
		for doc in AssetManager.documents:
			if doc.instances != doc.committed:
				entry.append((doc, doc.committed));
				doc.committed = copy.deepcopy(doc.instances);
		if len(entry) == 0:
			return False;
		History.undo_stack.append(entry);
		del History.undo_stack[:-History.LIMIT];
		History.redo_stack.clear();
		return True;

	def tick(idle):
		"""Call once per frame. `idle` should be true when no widget is active and no
		mouse button is held, so a drag or a text edit becomes one entry, not many.
		Commits on the transition to idle, and every IDLE_COMMIT_INTERVAL frames while
		idle to catch edits made purely via keyboard shortcuts."""
		History._frame += 1;
		if idle and (not History._was_idle or History._frame % History.IDLE_COMMIT_INTERVAL == 0):
			History.commit();
		History._was_idle = idle;

	def _apply(entry):
		# Precondition: every doc is committed, so doc.committed == doc.instances.
		inverse = [];
		for doc, snapshot in entry:
			inverse.append((doc, doc.committed));
			restore_in_place(doc.instances, snapshot);
			doc.committed = snapshot;
			doc.on_restored();
		return inverse;

	def undo():
		History.commit(); # capture anything not yet committed so it is the first thing undone
		if len(History.undo_stack) == 0:
			return False;
		History.redo_stack.append(History._apply(History.undo_stack.pop()));
		return True;

	def redo():
		History.commit(); # any new edit since the undo clears the redo stack
		if len(History.redo_stack) == 0:
			return False;
		History.undo_stack.append(History._apply(History.redo_stack.pop()));
		return True;

def make_backups(dir, cold=True):
	dir = Path(dir);
	dir.mkdir(parents=True, exist_ok=True);

	docs: list[AssetDocument] = AssetManager.documents;
	for doc in docs:
		path = dir/doc.path.name;
		if cold:
			shutil.copy2(doc.path, path);
		else:
			doc.save(path);