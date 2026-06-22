import OpenGL;
OpenGL.FULL_LOGGING = True;
from OpenGL.GL import *;
from imgui_bundle import imgui;
import math;
from enum import Enum;
import copy;
import numpy as np;
import pathlib;

class EEID:
	def __iter__(self):
		self.eeid = 0;
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

def foldr(f, acc, xs):
	if len(xs) == 0:
		return acc;
	else:
		h, t = xs[0], xs[1:];
		return f(h, foldr(f, acc, t));

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
			(structure[part], path, value);

def make_texture(buffer, width, height):
	texture = glGenTextures(1);
	glBindTexture(GL_TEXTURE_2D, texture);
	glTexParameteri(GL_TEXTURE_2D, 	GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, 	GL_TEXTURE_MAG_FILTER, GL_NEAREST);
	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, buffer);
	return texture;

def process_trash(collection, trash, indices=False):
	if len(collection) == 0 or len(trash) == 0:
		return;
	while len(trash) > 0:
		t = trash.pop();
		if indices:
			del collection[t];
		else:
			collection.remove(t);

class SelectionContext:
	def __init__(self):
		self.selections = [];
		self.env = {};

	def clear(self):
		self.selections = [];
		self.env = {};
	
	def select(self, item, exclusive=False):
		if exclusive:
			self.selections = [];
		self.selections.append(item);

	def deselect(self, item):
		if item in self.selections:
			self.selections.remove(item);
	
	def is_selected(self, item):
		return item in self.selections;

	def get_selection(self, single=False):
		if single:
			return self.selections[-1] if len(self.selections) > 0 else None;
		return self.selections;
	
	def env_set(self, key, value):
		self.env[key] = value;

	def env_get(self, key):
		if not key in self.env:
			return None;
		return self.env[key];

class Clipboard:
	class CopyMode(Enum):
		NONE = 0
		SHALLOW = 1
		DEEP = 2
	
	def __init__(self):
		self.contents = [];

	def clear(self):
		self.contents.clear();

	def copy(self, value, copy_mode=CopyMode.NONE, exclusive=False):
		if exclusive:
			self.contents.clear();
		match copy_mode:
			case Clipboard.CopyMode.NONE:
				self.contents.append(value);
			case Clipboard.CopyMode.SHALLOW:
				self.contents.append(copy.copy(value));
			case Clipboard.CopyMode.DEEP:
				self.contents.append(copy.deepcopy(value));

	def paste(self, destination):
		for entry in self.contents:
			destination.append(entry);

class Trash:
	class DeleteItemRequest:
		def __init__(self, source, item):
			self.source = source;
			self.item = item;
	class DeleteIndexRequest:
		def __init__(self, source, index):
			self.source = source;
			self.index = index;
	class Record:
		def __init__(self, source, item):
			self.source = source;
			self.item = copy.deepcopy(item);
	
	def __init__(self, deferred):
		self.deferred = deferred;
		self.buffer = [];
		self.contents = [];
	
	def flush(self):
		while len(self.buffer) > 0:
			request = self.buffer.pop(0);
			if isinstance(request, Trash.DeleteItemRequest):
				self.contents.append(Trash.Record(request.source, request.item));
				request.source.remove(request.item);
			elif isinstance(request, Trash.DeleteIndexRequest):
				self.contents.append(Trash.Record(request.source, request.source[request.index]));
				del request.source[request.index];
	
	def clear(self):
		self.contents.clear();

	def trash_item(self, source, item):
		self.buffer.append(Trash.DeleteItemRequest(source, item));
		if not self.deferred:
			self.flush();
	def trash_index(self, source, index):
		self.buffer.append(Trash.DeleteIndexRequest(source, index));
		if not self.deferred:
			self.flush();

	def restore(self):
		if len(self.contents) > 0:
			record = self.contents.pop();
			record.source.append(record.item);
	def restore_all(self):
		while len(self.contents) > 0:
			self.restore();