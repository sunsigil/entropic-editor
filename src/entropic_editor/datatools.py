import json;
from pathlib import Path;

def read_json(file_path, data_path):
	file_path = Path(file_path);
	data_path = Path(data_path);

	with open(file_path, "r") as file:
		data = json.load(file);
		keys = list(data_path.parts);
		while len(keys) > 0:
			key = keys.pop(0);
			if key in data:
				data = data[key];
			else:
				return None;
		return data;