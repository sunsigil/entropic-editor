#!/usr/bin/env python3

import abc;
import re;
import glob;
import pathlib;

class Type(abc.ABC):
	@abc.abstractmethod
	def prototype(self):
		pass;
	@abc.abstractmethod
	def validate(self, value) -> bool:
		pass;
	@abc.abstractmethod
	def rectify(self, value):
		pass;

class Primitive(Type):
	pass;
class Int(Primitive):
	def __repr__(self):
		return "Int";
	def prototype(self) -> int:
		return 0;
	def validate(self, value) -> bool:
		return isinstance(value, int);
	def rectify(self, value):
		return int(value);
class Float(Primitive):
	def __repr__(self):
		return "Float";
	def prototype(self) -> float:
		return 0;
	def validate(self, value) -> bool:
		return isinstance(value, float);
	def rectify(self, value):
		return float(value);
class Bool(Primitive):
	def __repr__(self):
		return "Bool";
	def prototype(self) -> bool:
		return False;
	def validate(self, value) -> bool:
		return isinstance(value, bool);
	def rectify(self, value):
		return bool(value);
class String(Primitive):
	def __repr__(self):
		return "String";
	def prototype(self) -> str:
		return "";
	def validate(self, value) -> bool:
		return isinstance(value, str);
	def rectify(self, value):
		return str(value);
class Colour(Primitive):
	def __repr__(self):
		return "Colour";
	def prototype(self) -> list[int]:
		return [255, 255, 255];
	def validate(self, value) -> bool:
		return isinstance(value, list[int]) and len(value) == 3;
	def rectify(self, value):
		return value;
class Vec2(Primitive):
	def __repr__(self):
		return f"Vec2";
	def prototype(self) -> list[int]:
		return [0, 0];
	def validate(self, value) -> bool:
		return isinstance(value, list[int]) and len(value) == 2;
	def rectify(self, value):
		return value;
class Any(Primitive):
	def __repr__(self):
		return "Any";
	def prototype(self):
		return None;
	def validate(self, value) -> bool:
		return True;
	def rectify(self, value):
		return value;

class Enum(Type):
	def __init__(self, expression):
		parse_regex = r"enum|\(|,|\s|\)";
		values = re.split(parse_regex, expression);
		values = [v for v in values if len(v) > 0];
		self.values = values;
	def __repr__(self):
		return f"Enum({", ".join(self.values)})";
	def prototype(self) -> str:
		return self.values[0];
	def validate(self, value) -> bool:
		return value in self.values;
	def rectify(self, value):
		if value not in self.values:
			value = self.values[0];
		return value;

class Flags(Type):
	def __init__(self, expression):
		parse_regex = r"flags|\(|,|\s|\)";
		values = re.split(parse_regex, expression);
		values = [v for v in values if len(v) > 0];
		self.values = values;
	def __repr__(self):
		return f"Flags({", ".join(self.values)})";
	def prototype(self) -> str:
		return [];
	def validate(self, value) -> bool:
		error = next((x for x in value if not x in self.values), None);
		return error == None;
	def rectify(self, value):
		value = [x for x in value if x in self.values];
		return value;

class File(Type):
	def __init__(self, pattern):
		self.pattern = pattern;
		self.regex = glob.translate(self.pattern);
	def __repr__(self):
		return f"File({self.pattern})";
	def prototype(self) -> str:
		return "";
	def validate(self, value) -> bool:
		return re.match(self.regex, value);
	def rectify(self, value):
		return value;

class Asset(Type):
	def __init__(self, name):
		self.name = name;
	def __repr__(self):
		return f"Asset({self.name})";
	def prototype(self) -> str:
		return "";
	def validate(self, value) -> bool:
		return isinstance(value, str);
	def rectify(self, value):
		return value;

class List(Type):
	def __init__(self, T):
		self.T = T;
	def __repr__(self):
		return f"List({self.T})";

	def prototype(self) -> list:
		if isinstance(self.T, List):
			return [self.T.prototype()];
		else:
			return [];

	def validate(self, value) -> bool:
		if not isinstance(value, list):
			return False;
		valid = True;
		for item in value:
			valid = valid and self.T.validate(item);
		return valid;

	def rectify(self, value):
		return [self.T.rectify(x) for x in value];

	def get_inmost_type(self):
		T = self.T;
		while isinstance(T, List):
			T = T.T;
		return T;

class Object(Type):
	def __init__(self, elements):
		self.elements : list[Element] = elements;
	def __repr__(self):
		return f"Object({", ".join([str(e.T) for e in self.elements])})";
	
	def prototype(self) -> dict:
		instance = {};
		for element in self.elements:
			instance[element.name] = element.prototype();
		return instance;

	def validate(self, value) -> bool:
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

class Element:
	def __init__(self, name, T, attributes = [], conditions = []):
		self.name = name;
		self.T = T;
		self.attributes = attributes;
		self.conditions = conditions;
	
	def __repr__(self):
		return f"Element({self.name}, {self.T})";

	def get_attribute(self, attribute) -> bool:
		if attribute in self.attributes:
			return True;
		for a in self.attributes:
			if isinstance(a, dict) and attribute in a:
				return a[attribute];
		return None;

	def prototype(self):
		default_value = self.get_attribute("default-value");
		if default_value != None:
			return default_value;

		fixed_length = self.get_attribute("fixed-length");
		if fixed_length != None and isinstance(self.T, List):
			return [self.T.T.prototype() for i in range(fixed_length)];

		return self.T.prototype();

	def validate(self, value) -> bool:
		return self.T.validate(value);

	def search(self, path):
		if isinstance(path, str):
			path = pathlib.PurePosixPath(path);
		if isinstance(path, pathlib.PurePosixPath):
			path = [x for x in list(path.parts) if x != "."];
		if len(path) == 0:
			return self;
		
		part = path.pop(0);
		if isinstance(self.T, Object):
			for child in self.T.elements:
				if child.name == part:
					return child.search(path);
		
		return None;

def construct_type(expr) -> Type:
	if isinstance(expr, list):
		return List(construct_type(expr[0]));

	if isinstance(expr, dict):
		elements = [];
		for name in expr:
			element_expr = expr[name];
			element = construct_element(name, element_expr);
			elements.append(element);
		return Object(elements);

	if isinstance(expr, str):
		match expr:
			case "int":
				return Int();
			case "float":
				return Float();
			case "bool":
				return Bool();
			case "string":
				return String();
			case "colour":
				return Colour();
			case "vec2":
				return Vec2();
			case "any":
				return Any();

		if re.match(r"enum\(([A-z0-9_]+)+(\,+\s*[A-z0-9_]+)*\)", expr):
			return Enum(expr);
		if re.match(r"flags\(([A-z0-9_]+)+(\,+\s*[A-z0-9_]+)*\)", expr):
			return Flags(expr);

		if re.match(r"\*.[A-z]+", expr):
			return File(expr);

	return Asset(expr);

def compare_types(a, b):
	if type(a) == type(b):
		if isinstance(a, Object):
			if len(a.elements) != len(b.elements):
				return False;
			equal = True;
			for i in range(len(a.elements)):
				equal &= compare_types(a.elements[i].T, b.elements[i].T);
			return equal;
	
		elif isinstance(a, List):
			return compare_types(a.T, b.T);
	
		elif isinstance(a, Asset):
			return a.name == b.name;
	
		elif isinstance(a, File):
			return a.pattern == b.pattern;
	
		elif isinstance(a, Flags) or isinstance(a, Enum):
			equal = True;
			for i in range(len(a.values)):
				equal &= a.values[i] == b.values[i];
			return equal;
		return True;

	return False;

def construct_element(name, expr) -> Element:
	T = construct_type(expr["type"]);
	attributes = expr["attributes"] if "attributes" in expr else [];
	conditions = expr["conditions"] if "conditions" in expr else [];
	return Element(name, T, attributes, conditions);

class TNode:	
	def __init__(self, parent: TNode, enode: Element, inode):
		self.parent = parent;
		self.update(enode, inode);
	
	def update(self, enode: Element, inode):
		self.enode = enode;
		self.inode = inode;
		self.children = {};
		if isinstance(self.enode.T, Object):
			for child in self.enode.T.elements:
				self.children[child.name] = TNode(
					self,
					child,
					self.inode[child.name] if self.inode != None and child.name in self.inode else None
				);

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
			return None;

		if part in self.children:
			return self.children[part].search(path);
		
		return None;

class TypeHelper:
	def __init__(self, name, expr):
		self.abstract_tree = construct_element(name, expr);
	
	def search(self, path):
		return self.abstract_tree.search(path);

	def _evaluate_conditions(self, tnode) -> bool:
		conditions = tnode.enode.conditions;
		evaluation = True;
		for condition in conditions:
			crux = tnode.search(condition["key"]);
			evaluation &= crux != None and crux.inode == condition["value"];
		return evaluation;
	
	def _rectify(self, tnode):
		if not isinstance(tnode.enode.T, Object):
			return;
	
		# Exclusion pass
		canon_keys = [name for name in tnode.children];
		violations = [];
		for key in tnode.inode:
			if not key in canon_keys:
				violations.append(key);
		for key in violations:
			del tnode.inode[key];

		# Requirement pass
		for name,child in tnode.children.items():
			if child.inode == None:
				child.update(child.enode, child.enode.prototype());

		# Propagation pass
		for name,child in tnode.children.items():
			self._rectify(child);
	
		# Conditions pass
		violations = [];
		for name,child in tnode.children.items():
			if not self._evaluate_conditions(child):
				violations.append(name);
		for name in violations:
			del tnode.children[name];
	
		# Sparingly correcting primitives and lists of primitives
		# Be really careful trying to do this to more complex types
		if isinstance(tnode.enode.T, Primitive) or (
			isinstance(tnode.enode.T, List) and isinstance(tnode.enode.T.get_inmost_type(), Primitive)
		):
			tnode.inode = tnode.enode.T.rectify(tnode.inode);

	def rectify(self, instance):
		self._rectify(TNode(None, self.abstract_tree, instance));

class TypeRegistry:
	entries = {};
	def register(name, type):
		if not TypeRegistry.has(name):
			TypeRegistry.entries[name] = type;
	def has(name):
		return name in TypeRegistry.entries;
	def get(name):
		if TypeRegistry.has(name):
			return TypeRegistry.entries[name];
		return construct_type(name);