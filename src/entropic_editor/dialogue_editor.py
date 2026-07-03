from imgui_bundle import imgui, imgui_node_editor as imnodes;
from assets import AssetManager;
from cowtools import *;
import editor_gui as gui;
import asset_types;


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
	def __init__(self, node):
		self.asset = node;
		self.node_id = imnodes.NodeId(id(node));
		self.in_id = next(pid);
		self.out_ids = [];
		for edge in node["edges"]:
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
		return self.by_name[name];

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
	tree = [];
	stack = [node];
	visited = set();

	while len(stack) > 0:
		head = stack.pop(-1);
		tree.append(head);
		visited.add(id(head));
		for edge in head["edges"]:
			next_node = AssetManager.search("dialogue", edge["node"]);
			if next_node != None and not id(next_node) in visited:
				stack.append(next_node);
	
	return tree;

class DialogueEditor:
	def __init__(self):
		self.context = imnodes.create_editor();

		self.node_bank = AssetManager.get_all("dialogue");	
		self.source_bank = find_sources();
		self.root = None;

		self.tree = [];
		self.links = [];
	
		self.trash = Trash(deferred=True);
	
	def __del__(self):
		imnodes.destroy_editor(self.context);
	
	def load_root(self, node):
		self.root = node;
		self.tree = populate_tree(self.root);
	
	def menu_bar(self):
		if imgui.begin_menu_bar():
			if imgui.begin_menu("File"):
				if imgui.begin_menu("Open"):

					if imgui.begin_menu("Source"):
						for source in self.source_bank:
							if imgui.menu_item(source["name"], "", source == self.root)[1]:
								self.load_root(source);
						imgui.end_menu();
					
					if imgui.begin_menu("All"):
						for node in self.node_bank:
							if imgui.menu_item(node["name"], "", node == self.root)[1]:
								self.load_root(node);
						imgui.end_menu();
					
					imgui.end_menu();
				imgui.end_menu();
			imgui.end_menu_bar();
	
	def draw_inspector(self):
		if imgui.begin_menu("Add node"):
			if imgui.begin_menu("Existing"):
				for node in self.node_bank:
					if imgui.menu_item_simple(node["name"]):
						tree = populate_tree(node);
						for x in tree:
							if not x in self.tree:
								self.tree.append(x);
				imgui.end_menu();
			if imgui.menu_item_simple("New"):
				new = AssetManager.get_document("dialogue").spawn_entry();
				self.tree.append(new);
			imgui.end_menu();
	
	def draw_node(self, node):
		def get_max_line_width(pad):
			n = max([len(x) for x in node.asset["lines"]]) if len(node.asset["lines"]) > 0 else 0;
			return n * 8 + pad;
		def get_edge_width(edge, pad):
			return len(edge["text"]) * 8 + pad;
	
		imnodes.begin_node(node.node_id);
		imgui.push_id(str(id(node.asset)));
		
		imnodes.begin_pin(node.in_id, imnodes.PinKind.input);
		imgui.text("(In)");
		imnodes.end_pin();

		imgui.same_line();
		name_w = len(node.asset["name"]) * 8 + 36;
		imgui.set_next_item_width(name_w);
		node.asset["name"] = gui.input_string("##name", node.asset["name"]);

		imgui.begin_group();
		imgui.push_id("lines");
		line_w = max(16, get_max_line_width(4));
		for idx, line in enumerate(node.asset["lines"]):
			imgui.push_id(str(idx));

			imgui.set_next_item_width(line_w);
			node.asset["lines"][idx] = gui.input_string(f"##line{idx}", line);

			imgui.same_line();
			if imgui.button("-"):
				self.trash.trash_index(node.asset["lines"], idx);
		
			imgui.pop_id();

		if imgui.button("New line"):
			node.asset["lines"].append(AssetManager.get_tree("dialogue").search("lines").T.inmost.prototype());
		
		imgui.pop_id();
		imgui.end_group();
		imgui.dummy((line_w, 0));

		imgui.begin_group();
		imgui.push_id("edges");
		for idx, edge in enumerate(node.asset["edges"]):
			imgui.push_id(str(idx));

			edge_w = max(16, get_edge_width(edge, 4));
			imgui.dummy((line_w-edge_w, 0));
			imgui.same_line();
			imgui.set_next_item_width(edge_w);
			edge["text"] = gui.input_string(f"##edge{idx}", edge["text"]);

			imgui.same_line();
			if imgui.button("-"):
				self.trash.trash_index(node.asset["edges"], idx);

			imgui.same_line();
			imnodes.begin_pin(node.out_ids[idx], imnodes.PinKind.output);
			imgui.text("(Out)");
			imnodes.end_pin();
		
			imgui.pop_id();
		
		if imgui.button("New edge"):
			node.asset["edges"].append(AssetManager.get_tree("dialogue").search("edges").T.inmost.prototype());
		
		imgui.pop_id();
		imgui.end_group();
		imgui.dummy((line_w, 0));

		imgui.pop_id();
		imnodes.end_node();
	
	def draw_graph(self):
		GenID.reset_frame_ids();

		registry = GraphRegistry();
		for node in self.tree:
			registry.register_node(GraphNode(node));
		
		for node in registry.nodes:
			for idx, edge in enumerate(node.asset["edges"]):
				if edge["node"] != "":
					next_node = registry.search_by_name(edge["node"]);
					if next_node != None:
						registry.register_edge(GraphEdge(node.out_ids[idx], next_node.in_id));

		imnodes.set_current_editor(self.context);
		imnodes.begin("graph", imgui.ImVec2(0, 0));

		for node in registry.nodes:
			self.draw_node(node);
		
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