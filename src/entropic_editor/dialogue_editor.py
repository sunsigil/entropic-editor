from imgui_bundle import imgui, imgui_node_editor as imnodes;
from assets import AssetManager;
from cowtools import *;
import editor_gui as gui;
import random as rand;
import input;
import glfw;

#########################################################
## UNIVERSAL DIALOGUE GUI

NODE_WIDTH = 256

def gui_newline(width=NODE_WIDTH):
	imgui.dummy((width, 8));

def gui_input_line(line, width=NODE_WIDTH):
	imgui.set_next_item_width(width);
	imgui.begin_group();
	imgui.push_id(str(id(line)));

	imgui.set_next_item_width(width);
	line["text"] = gui.input_string("Text", line["text"], True);
	imgui.set_next_item_width(width);
	line["script"] = gui.input_string("Script", line["script"], True);

	imgui.pop_id();
	imgui.end_group();

def gui_input_edge(edge, pin_id, width=NODE_WIDTH):
	imgui.set_next_item_width(width);
	imgui.begin_group();
	imgui.push_id(str(id(edge)));
	
	text_width = max(64, len(edge["text"]) * 8 + 32);
	imgui.dummy((width-text_width, 0));
	imgui.same_line();
	imgui.set_next_item_width(text_width);
	edge["text"] = gui.input_string("##text", edge["text"]);

	imgui.same_line();
	imnodes.begin_pin(pin_id, imnodes.PinKind.output);
	imgui.text("(Out)");
	imnodes.end_pin();

	imgui.dummy((width-text_width, 0));
	imgui.same_line();
	imgui.set_next_item_width(text_width);
	edge["condition"] = gui.input_string("Condition", edge["condition"], long=True);

	imgui.pop_id();
	imgui.end_group();

def gui_node(node):
	imnodes.begin_node(node.node_id);
	imgui.push_id(str(id(node.asset)));
	
	imnodes.begin_pin(node.in_id, imnodes.PinKind.input);
	imgui.text("(In)");
	imnodes.end_pin();

	imgui.same_line();
	node.asset["face"] = gui.input_sprite("##face", node.asset["face"], (32, 32));

	imgui.same_line();
	imgui.set_next_item_width(NODE_WIDTH);
	node.asset["name"] = gui.input_string("##name", node.asset["name"]);
	gui_newline();

	imgui.begin_group();
	for idx, line in enumerate(node.asset["lines"]):
		gui_input_line(line);
	if imgui.button("New line"):
		node.asset["lines"].append(AssetManager.get_tree("dialogue").search("lines").inmost.prototype());
	imgui.end_group();
	gui_newline();

	imgui.begin_group();
	for idx, edge in enumerate(node.asset["edges"]):
		gui_input_edge(edge, node.out_ids[idx]);
	if imgui.button("New edge"):
		node.asset["edges"].append(AssetManager.get_tree("dialogue").search("edges").inmost.prototype());
	imgui.end_group();
	gui_newline();

	imgui.pop_id();
	imnodes.end_node();

#########################################################
## DIALOGUE GRAPH

class GenID:
	eeid = iter(EEID());

	def __init__(self, cast_type):
		self.cast_type = cast_type;
	
	def __iter__(self):
		return self;

	def __next__(self):
		return self.cast_type((next(GenID.eeid)));

	def reset_frame_ids():
		GenID.eeid = iter(EEID());
		GenID.eeid.__next__();

pid = GenID(imnodes.PinId);
lid = GenID(imnodes.LinkId);

class GraphNode:
	def __init__(self, node, position=None):
		self.asset = node;
		self.node_id = imnodes.NodeId(id(node));
		self.in_id = next(pid);
		self.out_ids = [];
		for edge in node["edges"]:
			self.out_ids.append(next(pid));

		self.position = position;

	def refresh(self):
		self.in_id = next(pid);
		self.out_ids = [];
		for edge in self.asset["edges"]:
			self.out_ids.append(next(pid));

class GraphEdge:
	def __init__(self, out_id, in_id):
		self.link_id = next(lid);
		self.out_id = out_id;
		self.in_id = in_id;

class GraphRegistry:
	def __init__(self):
		self.nodes = [];
		self.edges = [];

		self.by_name = {};
		self.by_node_id = {};
		self.by_pin_id = {};
		self.by_link_id = {};
	
	def register_node(self, node):
		self.nodes.append(node);
		self.by_name[node.asset["name"]] = node;
		self.by_node_id[node.node_id.id()] = node;
		self.by_pin_id[node.in_id.id()] = node;
		for pin_id in node.out_ids:
			self.by_pin_id[pin_id.id()] = node;
	
	def register_edge(self, edge):
		self.edges.append(edge);
		self.by_link_id[edge.link_id.id()] = edge;
	
	def search_by_name(self, name):
		if name in self.by_name:
			return self.by_name[name];
		else:
			return None;

	def search_by_node_id(self, node_id):
		return self.by_node_id[node_id.id()];

	def search_by_pin_id(self, pin_id):
		return self.by_pin_id[pin_id.id()];

	def search_by_link_id(self, link_id):
		return self.by_link_id[link_id.id()];

def find_sources():
	nodes = AssetManager.get_all("dialogue");
	sources = [];
	for a in nodes:
		source = True;
		for b in nodes:
			for edge in b["edges"]:
				if edge["node"] == a["name"]:
					source = False;
					break;
			if not source:
				break;
		if source:
			sources.append(a);
	return sources;

def populate_tree(node):
	graph = [];
	stack = [node];
	visited = set(node["name"]);

	while len(stack) > 0:
		head = stack.pop(-1);
		graph.append(GraphNode(head));
		for edge in head["edges"]:
			next_node = AssetManager.search("dialogue", edge["node"]);
			if next_node != None and not next_node["name"] in visited:
				stack.append(next_node);
				visited.add(next_node["name"]);
	
	return graph;

class DialogueEditor:
	def __init__(self):
		self.context = imnodes.create_editor();

		self.node_bank = AssetManager.get_all("dialogue");	
		self.source_bank = find_sources();

		self.root = None;
		self.nodes = [];
		self.links = [];
		self.dirty = False;
	
		self.trash = Trash(deferred=True);
	
	def __del__(self):
		imnodes.destroy_editor(self.context);
	
	def load_root(self, node):
		self.root = node;
		self.nodes = populate_tree(self.root);
		self.dirty = True;
	
	def menu_bar(self):
		if imgui.begin_menu_bar():
			if imgui.begin_menu("File"):
				if imgui.begin_menu("Open"):

					if imgui.begin_menu("Source"):
						for source in self.source_bank:
							clicked, status = imgui.menu_item(source["name"], "", source == self.root);
							if clicked and status:
								self.load_root(source);
						imgui.end_menu();
					
					if imgui.begin_menu("All"):
						for node in self.node_bank:
							clicked, status = imgui.menu_item(node["name"], "", node == self.root);
							if clicked and status:
								self.load_root(node);
						imgui.end_menu();
					
					imgui.end_menu();
				imgui.end_menu();
			imgui.end_menu_bar();
	
	def draw_inspector(self):
		if imgui.begin_menu("Graph"):
			if imgui.begin_menu("Add"):
				if imgui.menu_item_simple("New node"):
					new = AssetManager.get_document("dialogue").spawn_entry();
					size = imnodes.get_screen_size();
					w, h = size;
					self.nodes.append(GraphNode(new, imnodes.screen_to_canvas(imgui.ImVec2(w/2, h/2))));
				imgui.end_menu();
			imgui.end_menu();
	
	def draw_graph(self):
		GenID.reset_frame_ids();

		registry = GraphRegistry();
		for node in self.nodes:
			node.refresh();
			registry.register_node(node);
		
		for node in registry.nodes:
			for idx, edge in enumerate(node.asset["edges"]):
				if edge["node"] != "":
					next_node = registry.search_by_name(edge["node"]);
					if next_node != None:
						registry.register_edge(GraphEdge(node.out_ids[idx], next_node.in_id));

		imnodes.set_current_editor(self.context);
		imnodes.begin("graph", imgui.ImVec2(0, 0));

		for node in registry.nodes:
			gui_node(node);
		
		for edge in registry.edges:
			imnodes.link(edge.link_id, edge.out_id, edge.in_id);
		
		if imnodes.begin_create():
			in_id = imnodes.PinId();
			out_id = imnodes.PinId();
	
			if imnodes.query_new_link(out_id, in_id):
				if out_id and in_id:
					if imnodes.accept_new_item():
						out_node = registry.search_by_pin_id(out_id);
						out_edge_idx = out_node.out_ids.index(out_id);
						in_node = registry.search_by_pin_id(in_id);
						out_node.asset["edges"][out_edge_idx]["node"] = in_node.asset["name"];			
			imnodes.end_create();
		
		if imnodes.begin_delete():
			del_lid = imnodes.LinkId();
			while imnodes.query_deleted_link(del_lid):
				if imnodes.accept_deleted_item():
					edge = registry.search_by_link_id(del_lid);
					out_node = registry.search_by_pin_id(edge.out_id);
					out_idx = out_node.out_ids.index(edge.out_id);
					out_node.asset["edges"][out_idx]["node"] = "";
			imnodes.end_delete();
		
		if self.dirty:
			visited = [];
			def recursive_position(node, y0, x, y):
				if node.asset["name"] in visited:
					return False;
				visited.append(node.asset["name"]);

				node.position = imgui.ImVec2(x, y);
				w, h = imnodes.get_node_size(node.node_id);
				children = [registry.search_by_name(x["node"]) for x in node.asset["edges"]];
				y = y0;
				for child in children:
					if child != None:
						if recursive_position(child, y, x+w+64, y):
							y += h + 64;
				return True;
			recursive_position(registry.nodes[0], 0, 0, 0);
			self.dirty = False;
		for node in registry.nodes:
			if not node.position is None:
				imnodes.set_node_position(node.node_id, node.position);
				node.position = None;
		
		imnodes.end();

	def draw(self):
		self.menu_bar();

		gui.begin_column("inspector", imgui.get_content_region_avail().x * 0.125);
		self.draw_inspector();
		gui.end_column();

		gui.begin_column("graph");
		self.draw_graph();
		gui.end_column();

		self.trash.flush();