from imgui_bundle import imgui, imgui_node_editor as imnodes;
from assets import AssetManager;
from cowtools import *;
import editor_gui as gui;
from input import InputManager;
import glfw;

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
	WIDTH = 256;

	def __init__(self, asset, position=None, is_root=False):
		self.trash = Trash(deferred=True);

		self.asset = asset;

		self.node_id = imnodes.NodeId(id(asset));
		self.in_id = next(pid);
		self.out_ids = [];
		for edge in asset["edges"]:
			self.out_ids.append(next(pid));

		self.position = position;
		self.is_root = is_root;

	def refresh(self):
		self.in_id = next(pid);
		self.out_ids = [];
		for edge in self.asset["edges"]:
			self.out_ids.append(next(pid));

	def _newline(self, width=None):
		width = GraphNode.WIDTH if width == None else width;
		imgui.dummy((width, 8));

	def _draw_line(self, idx, width=None):
		line = self.asset["lines"][idx];
		width = GraphNode.WIDTH if width == None else width;

		imgui.set_next_item_width(width);
		imgui.begin_group();
		imgui.push_id(str(id(line)));

		imgui.set_next_item_width(width);
		line["text"] = gui.input_string("Text", line["text"], True);
		imgui.set_next_item_width(width);
		line["script"] = gui.input_string("Script", line["script"], True, True);

		imgui.pop_id();
		imgui.end_group();

		imgui.same_line();
		if imgui.button(f"-##line_{idx}"):
			self.trash.trash_index(self.asset["lines"], idx);

	def _draw_edge(self, idx, pin_id, width=None):
		edge = self.asset["edges"][idx];
		width = GraphNode.WIDTH if width == None else width;

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
		edge["condition"] = gui.input_string("Condition", edge["condition"], True, True);

		imgui.pop_id();
		imgui.end_group();

		imgui.same_line();
		if imgui.button(f"-##edge_{idx}"):
			self.trash.trash_index(self.asset["edges"], idx);

	def draw(self):
		imnodes.begin_node(self.node_id);
		imgui.push_id(str(id(self.asset)));
		
		imnodes.begin_pin(self.in_id, imnodes.PinKind.input);
		imgui.text("(In)");
		imnodes.end_pin();
	
		imgui.same_line();
		self.asset["face"] = gui.input_sprite("##face", self.asset["face"], (32, 32));
	
		if self.is_root:
			imgui.same_line();
			imgui.set_next_item_width(GraphNode.WIDTH);
			self.asset["name"] = gui.input_string("##name", self.asset["name"]);
			self._newline();
	
		imgui.begin_group();
		for idx, line in enumerate(self.asset["lines"]):
			self._draw_line(idx);
		if imgui.button("New line"):
			self.asset["lines"].append(AssetManager.get_tree("dialogue").search("lines").inmost.prototype());
		imgui.end_group();
		self._newline();
	
		imgui.begin_group();
		for idx, edge in enumerate(self.asset["edges"]):
			self._draw_edge(idx, self.out_ids[idx]);
		if imgui.button("New edge"):
			self.asset["edges"].append(AssetManager.get_tree("dialogue").search("edges").inmost.prototype());
		imgui.end_group();
		self._newline();
	
		imgui.pop_id();
		imnodes.end_node();

		self.trash.flush();

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
		return self.by_node_id[node_id.id()] if node_id.id() in self.by_node_id else None;

	def search_by_pin_id(self, pin_id):
		return self.by_pin_id[pin_id.id()] if pin_id.id() in self.by_pin_id else None;

	def search_by_link_id(self, link_id):
		return self.by_link_id[link_id.id()] if link_id.id() in self.by_link_id else None;

def find_sources():
	nodes = AssetManager.get_all("dialogue");
	targets = {edge["node"] for node in nodes for edge in node["edges"]};
	return [node for node in nodes if not node["name"] in targets];

def populate_tree(node):
	graph = [];
	stack = [node];
	visited = {node["name"]};
	root_face = node["face"];

	while len(stack) > 0:
		head = stack.pop(-1);
		if head["face"] == "":
			head["face"] = root_face;
		graph.append(GraphNode(head, is_root=head==node));
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

		self.root = None;
		self.nodes = [];
		self.links = [];
		self.dirty = False;
	
		self.trash = Trash(deferred=True);
		self.clipboard = Clipboard();
		self.selection_context = SelectionContext();
		self.canvas_focused = True;

		self.context_node = None;
		self.rename_target = None;
		self.rename_buffer = "";
		self.rename_pending = False;
		self.node_generation = AssetManager.get_document("dialogue").generation;

		names = [x["name"] for x in self.node_bank];
		anons = [int(x[1:]) for x in names if x[0] == "x" and x[1:].isnumeric()];
		anon_max = max(anons, default=-1);
		self.anon_id = EEID(anon_max+1);
	
	def __del__(self):
		imnodes.destroy_editor(self.context);
	
	def load_root(self, node):
		self.root = node;
		self.nodes = populate_tree(self.root);
		self.dirty = True;

	def resync(self):
		# History restores an undone/redone delete as a new dict, not the one
		# self.nodes was holding, so a document-level undo doesn't by itself
		# bring a deleted node back into the currently displayed graph.
		document = AssetManager.get_document("dialogue");
		if document.generation == self.node_generation:
			return;
		self.node_generation = document.generation;

		live = document.instances;
		self.nodes = [node for node in self.nodes if node.asset in live];

		known = {node.asset["name"] for node in self.nodes};
		grown = True;
		while grown:
			grown = False;
			for node in list(self.nodes):
				for edge in node.asset["edges"]:
					name = edge["node"];
					if name != "" and name not in known:
						target = AssetManager.search("dialogue", name);
						if target != None:
							self.nodes.append(GraphNode(target));
							known.add(name);
							grown = True;

		self.dirty = True;

	def begin_rename(self, instance):
		self.rename_target = instance;
		self.rename_buffer = instance["name"];
		# Popup IDs hash against the ID stack, so the popup must be opened
		# from window level rather than from inside the context menu.
		self.rename_pending = True;

	def draw_rename_modal(self):
		modal_id = "Rename node";
		if self.rename_pending:
			imgui.open_popup(modal_id);
			self.rename_pending = False;

		if self.rename_target == None:
			return;

		visible, _ = imgui.begin_popup_modal(modal_id, None, imgui.WindowFlags_.always_auto_resize);
		if not visible:
			self.rename_target = None;
			return;

		old_name = self.rename_target["name"];

		if imgui.is_window_appearing():
			imgui.set_keyboard_focus_here();
		imgui.set_next_item_width(256);
		submitted, self.rename_buffer = imgui.input_text(
			"##rename", self.rename_buffer, imgui.InputTextFlags_.enter_returns_true
		);

		new_name = self.rename_buffer.strip();
		collision = new_name != old_name and AssetManager.search("dialogue", new_name) != None;
		valid = len(new_name) > 0 and not collision;

		if collision:
			imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "Name already in use");
		elif len(new_name) == 0:
			imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "Name cannot be empty");

		imgui.begin_disabled(not valid);
		commit = imgui.button("Rename") or (submitted and valid);
		imgui.end_disabled();
		imgui.same_line();
		cancel = imgui.button("Cancel") or imgui.is_key_pressed(imgui.Key.escape);

		if commit:
			if new_name != old_name:
				AssetManager.rename("dialogue", old_name, new_name);
			self.rename_target = None;
			imgui.close_current_popup();
		elif cancel:
			self.rename_target = None;
			imgui.close_current_popup();

		imgui.end_popup();

	def menu_bar(self):
		if imgui.begin_menu_bar():
			if imgui.begin_menu("File"):
				if imgui.menu_item_simple("New source"):
					root = AssetManager.get_document("dialogue").spawn_entry();
					self.load_root(root);
				imgui.end_menu();

			if imgui.begin_menu("Graph"):
				if imgui.begin_menu("Add"):
					if imgui.menu_item_simple("New node"):
						new = AssetManager.get_document("dialogue").spawn_entry(name=f"x{next(self.anon_id)}");
						size = imnodes.get_screen_size();
						w, h = size;
						self.nodes.append(GraphNode(new, imnodes.screen_to_canvas(imgui.ImVec2(w/2, h/2))));
					imgui.end_menu();
				imgui.end_menu();
			imgui.end_menu_bar();
	
	# Every graph is identified by its source, the one node nothing points at.
	# Orphaned anonymous nodes are sources too, but not graphs anyone edits
	def draw_inspector(self):
		sources = find_sources();
		def is_graph(node):
			return node in sources and not node.get("metadata", {}).get("anonymous", False);
		root = gui.asset_selector("dialogue-selector", self.root, "dialogue", filter=is_graph);
		if root is not self.root:
			self.load_root(root);
	
	def draw_graph(self):
		GenID.reset_frame_ids();
		self.resync();

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

		self.selection_context.clear();
		selected_ids = imnodes.get_selected_nodes();
		for node_id in selected_ids:
			node = registry.search_by_node_id(node_id);
			if node != None:
				self.selection_context.select(node);
		
		if imgui.is_window_focused(imgui.WindowFlags_.child_window):
			if not self.selection_context.is_empty():
				self.canvas_focused = False;
				selection = self.selection_context.get_selection();
				if InputManager.is_command(glfw.KEY_C):
					self.clipboard.clear();
					for node in selection:
						self.clipboard.copy(node);
				if InputManager.is_command(glfw.KEY_D):
					for node in selection:
						self.trash.trash_item(self.nodes, node);
			else:
				if imnodes.is_background_clicked():
					self.canvas_focused = True;
				if self.canvas_focused and InputManager.is_command(glfw.KEY_V):
					for node in self.clipboard.contents:
						new = AssetManager.get_document("dialogue").spawn_entry(node.asset, name=f"x{next(self.anon_id)}");
						size = imnodes.get_screen_size();
						w, h = size;
						self.nodes.append(GraphNode(new, imnodes.screen_to_canvas(imgui.ImVec2(w/2, h/2))));

		for node in registry.nodes:
			node.draw();
		
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

		imnodes.suspend();
		context_node_id = imnodes.NodeId();
		if imnodes.show_node_context_menu(context_node_id):
			node = registry.search_by_node_id(context_node_id);
			if node != None:
				self.context_node = node;
				imgui.open_popup("node_context_menu");
		if imgui.begin_popup("node_context_menu"):
			node = self.context_node;
			if imgui.menu_item_simple("Rename"):
				self.begin_rename(node.asset);
			if imgui.menu_item_simple("Duplicate"):
				new = AssetManager.get_document("dialogue").spawn_entry(node.asset, name=f"x{next(self.anon_id)}");
				position = imnodes.get_node_position(node.node_id) + imgui.ImVec2(32, 32);
				self.nodes.append(GraphNode(new, position));
			if imgui.menu_item_simple("Delete"):
				AssetManager.get_document("dialogue").delete_entry(node.asset);
				self.trash.trash_item(self.nodes, node);
				if node.asset is self.root:
					self.root = None;
			imgui.end_popup();
		imnodes.resume();

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

		self.draw_rename_modal();

		self.trash.flush();
