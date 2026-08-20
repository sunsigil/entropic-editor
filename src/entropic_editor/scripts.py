import asset_types;
import re;
from pathlib import Path;
import hashlib;
import subprocess as sp;
import copy;
import os;

class ScriptDatum:
	pattern = r"--@scriptdata ([0-9A-Za-z_]+)\s*\:\s*([0-9A-Za-z_]+)";

	def __init__(self, key, type):
		self.key = key;
		self.type_expr = type;
		self.type = asset_types.construct_type(self.type_expr);

	def to_json(self, value=None):
		return {
			"signature": {
				"key": str(self.key),
				"type": str(self.type_expr),
			},
			"value": value
		};

def luac(luac_path, source, extra_args=[]):
	args = [luac_path];
	args += extra_args;
	args += ["-o", "-", "-"];
	return sp.run(args, input=source.encode(), capture_output=True, check=True).stdout;

class Script:
	luac_path = None;

	def __init__(self, source, name=None, debug=False):
		self.source = source.strip();
		self.name = name;

		self.bytecode = luac(Script.luac_path, self.source, [] if debug else ["-s"]);
		self.hash = hashlib.sha1(self.bytecode);

		if self.name == None:
			self.name = f"_{self.hash.hexdigest()[:12]}";

		sd_exprs = re.findall(ScriptDatum.pattern, self.source);
		self.script_data = [ScriptDatum(k, t) for k, t in sd_exprs];

	def export(self, path):
		path = Path(path);
		if not path.parent.exists():
			path.parent.mkdir(parents=True, exist_ok=True);
		file = open(path, "wb");
		file.write(self.bytecode);
		file.close();
	
	def __hash__(self):
		return int(self.hash.hexdigest(), 16);

class ScriptBank:
	class Record:
		def __init__(self, name, path):
			with open(path, "r") as file:
				self.path = path;
				self.timestamp = os.lstat(path).st_mtime;
				self.script = Script(file.read(), name);
	
	by_name = {};

	def update(name, path):
		path = Path(path);
		if not (path.exists() and path.is_file()):
			return;

		record = ScriptBank.by_name[name] if name in ScriptBank.by_name else None;
		timestamp = os.lstat(path).st_mtime;
		if record == None or record.timestamp != timestamp:
			ScriptBank.by_name[name] = ScriptBank.Record(name, path);
	
	def	refresh(script_assets, script_dir):
		for asset in script_assets:
			name = asset["name"];
			relative_path = asset["path"];
			real_path = script_dir / relative_path;
			ScriptBank.update(name, real_path);
	
	def search(name):
		return ScriptBank.by_name[name].script if name in ScriptBank.by_name else None;

def get_all_script_data(script_names):
	data = [];
	for name in script_names:
		script = ScriptBank.search(name);
		if script != None:
			entry = {
				"script": name,
				"data": [x.to_json() for x in script.script_data]
			};
			data.append(entry);
	return data;

def address_data(all_data, script, key):
	for entry in all_data:
		if entry["script"] == script:
			for datum in entry["data"]:
				if datum["signature"]["key"] == key:
					return datum;
	return None;

def validate_datum(datum):
	T_expr = datum["signature"]["type"];
	T = asset_types.construct_type(T_expr);
	return T.validate(datum["value"]);

def rectify_all_script_data(script_names, all_actual, all_reference=None):
	if all_reference == None:
		all_reference = get_all_script_data(script_names);
	all_merged = [];

	for script_data in all_reference:
		merged = [];

		script = script_data["script"];
		data = script_data["data"];
		keys = [x["signature"]["key"] for x in data];

		for key in keys:
			reference = address_data(all_reference, script, key);
			actual = address_data(all_actual, script, key);
			if actual == None:
				merged.append(copy.deepcopy(reference));
			elif not validate_datum(actual):
				T = asset_types.construct_type(actual["signature"]["type"]);
				actual["value"] = T.rectify(actual["value"]);
				merged.append(actual);
			else:
				merged.append(actual);

		all_merged.append({
			"script": script,
			"data": merged
		});

	return all_merged;