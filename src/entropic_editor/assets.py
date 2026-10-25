from pathlib import Path;
import json;
import asset_types;
import scripts;
import copy;
import shutil;

#########################################################
## DOCUMENT MODEL

keywords = [
	"instances",
	"metadata"
];

def is_asset_type_definition(key: str, value: dict):
	# An asset type may not be named by an asset document keyword
	if key in keywords:
		return False;
	# An asset type may not be an array type, and so can only be a dict
	if not isinstance(value, dict):
		return False;
	# An asset type must be an Object 
	if not "type" in value or not isinstance(value["type"], dict):
		return False;
	# We introspect no further
	# At this point, if the type expr is malformed,
	# it can at least be considered a malformed *type* expr
	return True;

def find_asset_type_definition(data: dict):
	if not isinstance(data, dict) or not "instances" in data:
		return None;
	for key in data:
		if is_asset_type_definition(key, data[key]):
			return key, data[key];
	return None;

def is_asset_document(path):
	with open(path, "r") as file:
		return find_asset_type_definition(json.load(file)) != None;

class AssetDocument:
	class IDPool:
		def __init__(self, document: "AssetDocument"):
			self.can_free = document.metadata.get("free_ids", False);
			self.allocated = set();
			self.max = -1;
			for instance in document.instances:
				if "id" in instance:
					self.allocate(instance["id"]);
		
		def allocate(self, i):
			self.allocated.add(i);
			self.max = max(self.max, i);
			return i;

		def free(self, i):
			if self.can_free:
				self.allocated.remove(i);
				self.max = max(self.allocated) if len(self.allocated) > 0 else -1;

		def allocate_free(self):
			limit = self.max+1;
			if self.can_free:
				for i in range(limit):
					if not i in self.allocated:
						return self.allocate(i);
			return self.allocate(limit);

	def __init__(self, path):
		self.path = Path(path);
		file = open(self.path, "r");
		data = json.load(file);
		file.close();

		type_def = find_asset_type_definition(data);
		if type_def == None:
			raise ValueError(f"{self.path} is not an asset document");

		self.data = data;
		self.instances = data.setdefault("instances", []);
		self.metadata = data.setdefault("metadata", {});

		self.type_name, type_data = type_def;
		type_tree = asset_types.construct_type(type_data["type"], type_data.get("attributes", {}));
		if not isinstance(type_tree, asset_types.Object):
			raise ValueError(f"{self.path}: asset type '{self.type_name}' is not an object type");
		self.type_tree = type_tree;

		if not "name" in self.type_tree.elements:
			self.type_tree.elements["name"] = asset_types.String();
		self.type_tree.elements["name"].read_only = True;

		self.id_pool = AssetDocument.IDPool(self);

		self.refresh();

		self.committed = copy.deepcopy(self.instances);
		self.generation = 0;

	
	def search(self, name):
		return next((x for x in self.instances if x["name"] == name), None);
	
	def spawn_entry(self, source=None, name=None):
		new = copy.deepcopy(source) if source != None else self.type_tree.prototype();

		new["name"] = f"new_{self.type_name}" if name == None else name;
		if "id" in new:
			new["id"] = self.id_pool.allocate_free();

		self.instances.append(new);
		return new;
	
	def delete_entry(self, entry):
		if "id" in entry:
			self.id_pool.free(entry["id"]);
		self.instances.remove(entry);

	def bind(self, instance):
		return asset_types.Binding(None, self.type_tree, instance);
	
	def is_dirty(self):
		return self.instances != self.committed;

	def refresh(self, changed_only=False):
		committed = self.committed if changed_only else None;
		for i, instance in enumerate(self.instances):
			if committed != None and i < len(committed) and instance == committed[i]:
				continue;
			self.bind(instance).rectify();
	
	def on_restored(self):
		self.id_pool = AssetDocument.IDPool(self);
		self.generation += 1;
	
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

	@classmethod
	def load_document(cls, path):
		try:
			document = AssetDocument(path);
			AssetManager.documents.append(document);
			AssetManager.document_map[document.type_name] = document;
			print(f"[AssetManager] Loaded {path}");
		except Exception as e:
			print(f"[AssetManager] Failed to load {path}!\n\t({e})");
			raise(e);			

	@classmethod
	def get_document(cls, asset_type) -> AssetDocument:
		if asset_type not in AssetManager.document_map:
			return None;
		return AssetManager.document_map[asset_type];

	@classmethod
	def rename(cls, asset_type, asset_name, new_name):
		asset = AssetManager.get_document(asset_type).search(asset_name);
		if asset == None:
			return;

		asset["name"] = new_name;

		for doc in AssetManager.documents:
			assets = AssetManager.get_document(doc.type_name).instances;
			for asset in assets:
				nodes = doc.bind(asset).flatten();
				for node in nodes:
					if node.I == None:
						continue;
					if isinstance(node.T, asset_types.List) and node.T.T == asset_types.Asset(asset_type):
						for i,v in enumerate(node.I):
							if v == asset_name:
								node.I[i]= new_name;
					if isinstance(node.T, asset_types.Object):
						for key in node.children:
							child = node.children[key];
							if child.T == asset_types.Asset(asset_type) and node.I.get(key) == asset_name:
								node.I[key] = new_name;

def rectify_entity_script_data(entity):
	prototype = AssetManager.get_document("prototype").search(entity["prototype"]);
	if prototype == None:
		return;
	prototype["script_data"] = scripts.rectify_all_script_data(prototype["scripts"], prototype["script_data"]);
	entity["script_data"] = scripts.rectify_all_script_data(prototype["scripts"], entity["script_data"], prototype["script_data"]);

# A datum equal to the prototype's old default is inherited (scenegen strips
# it), so it follows the new default; anything else is an override
def follow_prototype_defaults():
	prototypes = AssetManager.get_document("prototype");
	scenes = AssetManager.get_document("scene");
	if prototypes == None or scenes == None or prototypes.instances == prototypes.committed:
		return;

	entities = [entity for scene in scenes.instances for entity in scene["entities"]];
	for entity in entities:
		rectify_entity_script_data(entity);

	old = {prototype["name"]: prototype for prototype in prototypes.committed};
	for prototype in prototypes.instances:
		previous = old.get(prototype["name"]);
		if previous == None:
			continue;
		for block in prototype["script_data"]:
			for datum in block["data"]:
				key = datum["signature"]["key"];
				before = scripts.address_data(previous["script_data"], block["script"], key);
				if before == None or before["value"] == datum["value"]:
					continue;
				count = 0;
				for entity in entities:
					if entity["prototype"] != prototype["name"]:
						continue;
					actual = scripts.address_data(entity["script_data"], block["script"], key);
					if actual != None and actual["value"] == before["value"]:
						actual["value"] = copy.deepcopy(datum["value"]);
						count += 1;
				if count > 0:
					print(f"[Prototype] {prototype["name"]}.{block["script"]}.{key}: {count} entities followed {before["value"]} -> {datum["value"]}");

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
		follow_prototype_defaults();
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
