import re;
import glob;
import pathlib;
import json

class Type():
	def __init__(self, attributes={}):
		for key in attributes:
			setattr(self, key, attributes[key]);
	
	def __eq__(self, value):
		if type(self) == type(value):
			if isinstance(self, Object):
				if len(self.elements) != len(value.elements):
					return False;
				equal = True;
				for i in range(len(self.elements)):
					equal &= self.elements[i].T == value.elements[i].T;
				return equal;
		
			elif isinstance(self, List):
				return self.T == value.T;
		
			elif isinstance(self, Asset):
				return self.name == value.name;
		
			elif isinstance(self, File):
				return self.pattern == value.pattern;
		
			elif isinstance(self, Flags) or isinstance(self, Enum):
				equal = True;
				for i in range(len(self.values)):
					equal &= self.values[i] == value.values[i];
				return equal;
			return True;

		return False;

	def _prototype(self):
		raise NotImplementedError();
	def prototype(self):
		if hasattr(self, "default_value"):
			return self.default_value;
		return self._prototype();

	def validate(self, value) -> bool:
		raise NotImplementedError();
	def rectify(self, value):
		raise NotImplementedError();

	def search(self, path):
		if isinstance(path, str):
			path = pathlib.PurePosixPath(path);
		if isinstance(path, pathlib.PurePosixPath):
			path = [x for x in list(path.parts) if x != "."];
		if len(path) == 0:
			return self;

		part = path.pop(0);
		if isinstance(self, Object):
			if part in self.elements:
				element = self.elements[part];
				return element.search(path);
		
		return None;

class Primitive(Type):
	pass;

class Int(Primitive):
	def __repr__(self):
		return "Int";

	def _prototype(self) -> int:
		return int(0);

	def validate(self, value):
		return isinstance(value, int);
	def rectify(self, value):
		return int(value);

class Float(Primitive):
	def __repr__(self):
		return "Float";

	def _prototype(self):
		return float(0);

	def validate(self, value):
		return isinstance(value, float);
	def rectify(self, value):
		return float(value);

class Bool(Primitive):
	def __repr__(self):
		return "Bool";

	def _prototype(self):
		return False;

	def validate(self, value):
		return isinstance(value, bool);
	def rectify(self, value):
		return bool(value);

class String(Primitive):
	def __repr__(self):
		return "String";

	def _prototype(self):
		return "";

	def validate(self, value):
		return isinstance(value, str);
	def rectify(self, value):
		return str(value);

class Any(Primitive):
	def __repr__(self):
		return "Any";

	def _prototype(self):
		return None;

	def validate(self, value):
		return True;
	def rectify(self, value):
		return value;

class Enum(Type):
	def __init__(self, expression, attributes={}):
		super().__init__(attributes=attributes);
		parse_regex = r"enum|\(|,|\s|\)";
		values = re.split(parse_regex, expression);
		values = [v for v in values if len(v) > 0];
		self.values = values;
	def __repr__(self):
		return f"Enum({", ".join(self.values)})";

	def _prototype(self):
		return self.values[0];

	def validate(self, value):
		return value in self.values;
	def rectify(self, value):
		if value not in self.values:
			value = self.values[0];
		return value;

class Flags(Type):
	def __init__(self, expression, attributes={}):
		super().__init__(attributes=attributes);
		parse_regex = r"flags|\(|,|\s|\)";
		values = re.split(parse_regex, expression);
		values = [v for v in values if len(v) > 0];
		self.values = values;
	def __repr__(self):
		return f"Flags({", ".join(self.values)})";

	def _prototype(self):
		return [];

	def validate(self, value):
		error = next((x for x in value if not x in self.values), None);
		return error == None;
	def rectify(self, value):
		value = [x for x in value if x in self.values];
		return value;

class File(Type):
	def __init__(self, pattern, attributes={}):
		super().__init__(attributes=attributes);
		self.pattern = pattern;
		self.regex = glob.translate(self.pattern);
	def __repr__(self):
		return f"File({self.pattern})";

	def _prototype(self):
		return "";

	def validate(self, value):
		return re.match(self.regex, value);
	def rectify(self, value):
		return value;

class Asset(Type):
	def __init__(self, name, attributes={}):
		super().__init__(attributes=attributes);
		self.name = name;
	def __repr__(self):
		return f"Asset({self.name})";

	def _prototype(self):
		return "";

	def validate(self, value):
		return isinstance(value, str);
	def rectify(self, value):
		return value;

class List(Type):
	def __init__(self, T, attributes={}):
		super().__init__(attributes=attributes);
		self.T = T;
		T = self.T;
		while isinstance(T, List):
			T = T.T;
		self.inmost = T;

	def __repr__(self):
		return f"List({self.T})";

	def _prototype(self):
		if hasattr(self, "fixed_length"):
			return [self.T.prototype() for i in range(self.fixed_length)];
	
		if isinstance(self.T, List):
			return [self.T.prototype()];
		else:
			return [];

	def validate(self, value):
		if not isinstance(value, list):
			return False;
		valid = True;
		for item in value:
			valid = valid and self.T.validate(item);
		return valid;

	def rectify(self, value):
		return [self.T.rectify(x) for x in value];

class Object(Type):
	def __init__(self, elements, attributes={}):
		super().__init__(attributes=attributes);
		self.elements : dict[str, Type] = elements;
	def __repr__(self):
		return f"Object({", ".join([str(T) for T in self.elements.values()])})";
	
	def _prototype(self):
		instance = {};
		for name,T in self.elements.items():
			instance[name] = T.prototype();
		return instance;

	def validate(self, value):
		if not isinstance(value, dict):
			return False;
	
		exclusion_pass = True;
		canon_keys = [e.name for e in self.elements];
		for key in value:
			exclusion_pass &= key in canon_keys;
		if not exclusion_pass:
			return False;

		inclusion_pass = True;
		for element in self.elements:
			inclusion_pass &= element.name in value and element.validate(value[element.name]);
		if not inclusion_pass:
			return False;

		return True;

	def rectify(self, value):
		if not isinstance(value, dict):
			value = {};
		
		trash = [];
		for key in value:
			element = next((x for x in self.elements if x.name == key), None);
			if element == None:
				trash.append(key);
		for key in trash:
			del value[key];

		for element in self.elements:
			if not element.name in value:
				value[element.name] = element.T.prototype();
			else:
				value[element.name] = element.T.rectify(value[element.name]);

		return value;

class TypeRegistry:
	entries = {};

	def clear():
		TypeRegistry.entries.clear();

	def register(key, value):
		TypeRegistry.entries[key] = value;	

	def search(key):
		if key in TypeRegistry.entries:
			return TypeRegistry.entries[key];
		return None;

def load_typefile(path):
	file = open(path, "r");
	data = json.load(file);
	file.close();

	for name,expr in data.items():
		T = construct_type(expr["type"]);
		TypeRegistry.register(name, T);

	print("[Typefile] Loaded asset_types from", path);

def construct_type(expr, attributes={}) -> Type:
	if isinstance(expr, list):
		return List(construct_type(expr[0]), attributes=attributes);

	if isinstance(expr, dict):
		elements = {};
		for key in expr:
			subexpr = expr[key];
			attrs = subexpr["attributes"] if "attributes" in subexpr else {};
			elements[key] = construct_type(subexpr["type"], attributes=attrs);
		return Object(elements, attributes=attributes);

	if isinstance(expr, str):
		match expr:
			case "int":
				return Int(attributes=attributes);
			case "float":
				return Float(attributes=attributes);
			case "bool":
				return Bool(attributes=attributes);
			case "string":
				return String(attributes=attributes);
			case "any":
				return Any();

		if re.match(r"enum\(([A-z0-9_]+)+(\,+\s*[A-z0-9_]+)*\)", expr):
			return Enum(expr, attributes=attributes);
		if re.match(r"flags\(([A-z0-9_]+)+(\,+\s*[A-z0-9_]+)*\)", expr):
			return Flags(expr, attributes=attributes);

		if re.match(r"\*.[A-z]+", expr):
			return File(expr, attributes=attributes);

	registered = TypeRegistry.search(expr);
	if registered != None:
		return registered;

	return Asset(expr, attributes=attributes);

class MapNode:	
	def __init__(self, parent: MapNode, T: Type, I):
		self.parent = parent;
		self.update(T, I);
	def __repr__(self):
		return repr(self.T);
	
	def update(self, T: Type, I):
		self.T = T;
		self.I = I;

		if isinstance(T, Object):
			self.children = {};
			for key in T.elements:
				self.children[key] = MapNode(
					self,
					T.elements[key],
					I[key] if I != None and key in I else None
				);
		if isinstance(T, List):
			self.children = [];
			if I != None:
				for child in self.I:
					self.children.append(MapNode(
						self,
						T.T,
						child
					));

	def search(self, path):
		if isinstance(path, str):
			path = path.strip();
			if path[0] == "/":
				root = self;
				while root.parent != None:
					root = root.parent;
				return root.search(path[1:]);
			else:
				path = pathlib.PurePosixPath(path);
		if isinstance(path, pathlib.PurePosixPath):
			path = [x for x in list(path.parts) if x != "."];
		if len(path) == 0:
			return self;

		part = path.pop(0);
		if part == "..":
			if self.parent != None:
				return self.parent.search(path);
		else:
			if isinstance(self.children, dict) and part in self.children:
				return self.children[part].search(path);
			if isinstance(self.children, list) and int(part) >= 0 and int(part) < len(self.children):
				return self.children[int(part)].search(path);
		
		return None;

class TypeHelper:
	def __init__(self, T):
		self.root = T;
	
	def search(self, path):
		return self.root.search(path);

	def _evaluate_conditions(self, map_node) -> bool:
		if not hasattr(map_node.T, "conditions"):
			return True;
		conditions = map_node.T.conditions;
		evaluation = True;
		for condition in conditions:
			crux = map_node.search(condition["key"]);
			if crux == None or crux.I != condition["value"]:
				evaluation = False;
				break;
		return evaluation;
	
	def _rectify(self, map_node):
		if not hasattr(map_node, "children"):
			return;

		if isinstance(map_node.T, List):
			for child in map_node.children:
				self._rectify(child);
		
		if isinstance(map_node.T, Object):
			# Exclusion pass
			canon_keys = [key for key in map_node.children];
			violations = [];
			for key in map_node.I:
				if not key in canon_keys:
					violations.append(key);
			for key in violations:
				del map_node.I[key];

			# Requirement pass
			for key,child in map_node.children.items():
				if child.I == None:
					child.update(child.T, child.T.prototype());
					map_node.I[key] = child.I;

			# Propagation pass
			for key,child in map_node.children.items():
				self._rectify(child);
		
			# Conditions pass
			violations = [];
			for key,child in map_node.children.items():
				if not self._evaluate_conditions(child):
					violations.append(key);
			for key in violations:
				del map_node.children[key];
				del map_node.I[key];

	def rectify(self, instance):
		self._rectify(MapNode(None, self.root, instance));

	def _flatten(self, node: MapNode, acc):
		acc.append(node);
		if isinstance(node.T, List):
			for child in node.children:
				self._flatten(child, acc);
		if isinstance(node.T, Object):
			for key in node.children:
				self._flatten(node.children[key], acc);
	def flatten(self, instance):
		acc = [];
		self._flatten(MapNode(None, self.root, instance), acc);
		return acc;