import asset_types;
import re;
import assets;
import copy;
import context;

class ScriptData:
	pattern = r"--@scriptdata ([0-9A-Za-z_]+)\s*\:\s*([0-9A-Za-z_]+)";

	def __init__(self, key, type):
		self.key = key;
		self.type_expr = type;
		self.type = asset_types.construct_type(self.type_expr);

	def export(self):
		return {
			"key": str(self.key),
			"type": str(self.type_expr)
		};

class Script:
	def __init__(self, asset):
		self.asset = asset;
		self.refresh();
	
	def refresh(self):
		file = open(context.get().game_directory/"assets"/"scripts"/self.asset["path"], "r");
		self.text = file.read();

		sd_exprs = re.findall(ScriptData.pattern, self.text);
		self.script_data = [ScriptData(k, t) for k, t in sd_exprs];

	def rectify(self):
		self.asset["script_data"] = [x.export() for x in self.script_data];
	
def rectify_prototype(prototype):
	for script_name in prototype["scripts"]:
		script_asset = assets.AssetManager.search("script", script_name);
		if script_asset == None:
			continue;
		script = Script(script_asset);

		for sd in script.script_data:
			existing = next((x for x in prototype["script_data"] if x["signature"]["key"] == sd.key), None);
			exists = existing != None;
			if not exists:
				prototype["script_data"].append({
					"signature": sd.export(),
					"value": sd.type.prototype()
				});
			else:
				existing["signature"]["type"] = sd.type_expr;
				if not sd.type.validate(existing["value"]):
					existing["value"] = sd.type.rectify(existing["value"]);
	
def rectify_entity(entity):
		prototype = assets.AssetManager.search("prototype", entity["prototype"]);
		if prototype == None:
			return;
		rectify_prototype(prototype);

		valid_keys = [];
		for script_name in prototype["scripts"]:
			script_asset = assets.AssetManager.search("script", script_name);
			if script_asset == None:
				continue;
			script = Script(script_asset);

			for sd in script.script_data:
				existing = next((x for x in entity["script_data"] if x["signature"]["key"] == sd.key), None);
				exists = existing != None;
				if not exists:
					default = next(x for x in prototype["script_data"] if x["signature"]["key"] == sd.key);
					entity["script_data"].append(copy.copy(default));
				else:
					existing["signature"]["type"] = sd.type_expr;
					if not sd.type.validate(existing["value"]):
						existing["value"] = sd.type.rectify(existing["value"]);
				
				valid_keys.append(sd.key);
		
		trash = [];
		for sd_inst in entity["script_data"]:
			if sd_inst["signature"]["key"] not in valid_keys:
				trash.append(sd_inst);
		for sd_inst in trash:
			entity["script_data"].remove(sd_inst);

