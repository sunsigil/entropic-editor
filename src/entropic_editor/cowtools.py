from enum import Enum;
import copy;
import numpy as np;
import pathlib;

class EEID:
	def __init__(self, start=0):
		self.start = start;
		self.eeid = self.start;
	
	def __iter__(self):
		return self;

	def __next__(self):
		result = self.eeid;
		self.eeid += 1;
		return result;

def foldl(f, acc, xs):
	if len(xs) == 0:
		return acc;
	else:
		h, t = xs[0], xs[1:];
		return foldl(f, f(acc, h), t);

def clamp(v, a, b):
	return min(max(v, a), b);

def get_by_path(structure, path):
	if isinstance(path, str):
		path = pathlib.PurePosixPath(path);
	if isinstance(path, pathlib.PurePosixPath):
		path = [x for x in list(path.parts) if x != "."];
	if len(path) == 0:
		return structure;

	part = path.pop(0);
	if isinstance(structure, list) and part.isnumeric():
		return get_by_path(structure[int(part)], path);
	if part in structure:
		return get_by_path(structure[part], path);
	
	return None;

def set_by_path(structure, path, value):
	if isinstance(path, str):
		path = pathlib.PurePosixPath(path);
	if isinstance(path, pathlib.PurePosixPath):
		path = [x for x in list(path.parts) if x != "."];
	if len(path) == 0:
		return;

	part = path.pop(0);
	if isinstance(structure, list) and part.isnumeric():
		if len(path) == 0:
			structure[int(part)] = value;
		else:
			set_by_path(structure[int(part)], path, value);
	elif part in structure:
		if len(path) == 0:
			structure[part] = value;
		else:
			set_by_path(structure[part], path, value);

class SelectionContext:
	def __init__(self):
		self.selections = [];

	def clear(self):
		self.selections = [];
	
	def select(self, item, exclusive=False):
		if exclusive:
			self.selections = [];
		self.selections.append(item);

	def is_selected(self, item):
		return item in self.selections;

	def get_selection(self, single=False):
		if single:
			return self.selections[-1] if len(self.selections) > 0 else None;
		return self.selections;

	def is_empty(self):
		return len(self.selections) == 0;
	
class Clipboard:
	class CopyMode(Enum):
		NONE = 0
		DEEP = 1
	
	def __init__(self):
		self.contents = [];
		self.paste_count = 0;

	def clear(self):
		self.contents.clear();
		self.paste_count = 0;

	def copy(self, value, copy_mode=CopyMode.NONE, exclusive=False):
		if value == None:
			return;
		if exclusive:
			self.contents.clear();
		self.paste_count = 0;
		match copy_mode:
			case Clipboard.CopyMode.NONE:
				self.contents.append(value);
			case Clipboard.CopyMode.DEEP:
				self.contents.append(copy.deepcopy(value));

	def paste(self, destination):
		pasted = [];
		for entry in self.contents:
			pasted.append(copy.deepcopy(entry));
			destination.append(pasted[-1]);
		if len(pasted) > 0:
			self.paste_count += 1;
		return pasted;

	def is_empty(self):
		return len(self.contents) == 0;

class Trash:
	class DeleteItemRequest:
		def __init__(self, source, item):
			self.source = source;
			self.item = item;
	class DeleteIndexRequest:
		def __init__(self, source, index):
			self.source = source;
			self.index = index;

	def __init__(self):
		self.buffer = [];

	def flush(self):
		self.buffer.sort(reverse=True, key=lambda x: x.index if isinstance(x, Trash.DeleteIndexRequest) else 0);
		for request in self.buffer:
			if isinstance(request, Trash.DeleteItemRequest):
				if request.item in request.source:
					request.source.remove(request.item);
			elif isinstance(request, Trash.DeleteIndexRequest):
				if -len(request.source) <= request.index < len(request.source):
					del request.source[request.index];
		self.buffer = [];

	def trash_item(self, source, item):
		self.buffer.append(Trash.DeleteItemRequest(source, item));

	def trash_index(self, source, index):
		self.buffer.append(Trash.DeleteIndexRequest(source, index));
