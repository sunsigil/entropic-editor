from imgui_bundle import imgui, imgui_node_editor as imnodes;
from assets import AssetManager;
import editor_gui as gui;
from input import InputManager;
import glfw;
import dialogue;

#########################################################
## DIALOGUE GRAPH

EDGE_SLOTS_PER_NODE = 64
NODE_WIDTH = 256;

class Graph:
	def __init__(self, doc, root):
		self.doc = doc;
		self.root = root;
		self.buffer = [];

	def place(self, node):
		if not any(node is x for x in self.buffer):
			self.buffer.append(node);

	def remove(self, node):
		self.buffer = [x for x in self.buffer if x is not node];
		if node is self.root:
			self.root = None;

	def get_nodes(self):
		live_ids = {id(x) for x in self.doc.instances};
		if self.root != None and not id(self.root) in live_ids:
			self.root = None;
		self.buffer = [x for x in self.buffer if id(x) in live_ids];
		connected = dialogue.reachable_from(self.doc, [self.root]);
		connected_ids = {id(x) for x in connected};
		return connected + [x for x in self.buffer if not id(x) in connected_ids];

#########################################################
## IMNODES IDS

def get_base_id(node):
	return id(node) + 1;

def make_node_id(node):
	return imnodes.NodeId(get_base_id(node));

def make_in_pin_id(node):
	return imnodes.PinId(get_base_id(node) * EDGE_SLOTS_PER_NODE);

def make_out_pin_id(node, idx):
	assert idx + 1 < EDGE_SLOTS_PER_NODE;
	return imnodes.PinId(get_base_id(node) * EDGE_SLOTS_PER_NODE + idx + 1);

def make_link_id(node, idx):
	return imnodes.LinkId(get_base_id(node) * EDGE_SLOTS_PER_NODE + idx + 1);

# Inverse of the makers above. Returns (node, slot); slot 0 is the input
# pin, slot k+1 is the output pin of edge k. A link id is its output pin
# id, so this decodes links too.
def decode_pin(raw_id, by_base):
	base, slot = divmod(raw_id, EDGE_SLOTS_PER_NODE);
	return by_base.get(base), slot;

#########################################################
## POSITIONS

def set_position(node, x, y):
	x0, y0, x1, y1 = node["metadata"]["aabb"];
	node["metadata"]["aabb"] = [x, y, x + (x1 - x0), y + (y1 - y0)];

def push_aabb(node):
	x0, y0, _, _ = node["metadata"]["aabb"];
	imnodes.set_node_position(make_node_id(node), imgui.ImVec2(x0, y0));

def pull_aabb(node):
	nid = make_node_id(node);
	pos = imnodes.get_node_position(nid);
	size = imnodes.get_node_size(nid);
	# The aabb type is int-typed; imnodes floors positions, so this loses nothing.
	node["metadata"]["aabb"] = [int(pos.x), int(pos.y), int(pos.x + size.x), int(pos.y + size.y)];

def never_laid_out(nodes):
	return all(node["metadata"]["aabb"] == [0, 0, 0, 0] for node in nodes);

#########################################################
## NODE WIDGET

def _swap(items, a, b):
	items[a], items[b] = items[b], items[a];

def _newline(width=NODE_WIDTH):
	imgui.dummy((width, 8));

def _list_controls(node, key, idx, edits):
	items = node[key];
	imgui.same_line();
	if imgui.button(f"-##{key}_{idx}"):
		edits.append(lambda: items.pop(idx));
	imgui.same_line();
	imgui.begin_group();
	if imgui.arrow_button(f"up##{key}_{idx}", imgui.Dir.up) and idx > 0:
		edits.append(lambda: _swap(items, idx, idx-1));
	if imgui.arrow_button(f"down##{key}_{idx}", imgui.Dir.down) and idx < len(items)-1:
		edits.append(lambda: _swap(items, idx, idx+1));
	imgui.end_group();

def draw_line(node, idx, edits):
	line = node["lines"][idx];

	imgui.begin_group();
	imgui.push_id(str(id(line)));
	imgui.set_next_item_width(NODE_WIDTH);
	line["text"] = gui.input_string("Text", line["text"], True);
	imgui.set_next_item_width(NODE_WIDTH);
	line["script"] = gui.input_string("Script", line["script"], True, True);
	imgui.pop_id();
	imgui.end_group();

	_list_controls(node, "lines", idx, edits);

def draw_edge(node, idx, edits):
	edge = node["edges"][idx];
	text_width = max(64, len(edge["text"]) * 8 + 32);
	def right_align():
		imgui.dummy((NODE_WIDTH-text_width, 0));
		imgui.same_line();
		imgui.set_next_item_width(text_width);

	imgui.begin_group();
	imgui.push_id(str(id(edge)));

	right_align();
	imgui.begin_disabled(node["random"]);
	edge["text"] = gui.input_string("##text", edge["text"]);
	imgui.end_disabled();
	imgui.same_line();
	imnodes.begin_pin(make_out_pin_id(node, idx), imnodes.PinKind.output);
	imgui.text("(Out)");
	imnodes.end_pin();

	right_align();
	edge["condition"] = gui.input_string("Condition", edge["condition"], True, True);

	if node["random"]:
		right_align();
		edge["weight"] = gui.input_int("Weight", edge["weight"], low_bound=0, high_bound=255);

	imgui.pop_id();
	imgui.end_group();

	_list_controls(node, "edges", idx, edits);

def draw_node(node, doc):
	edits = [];

	imnodes.begin_node(make_node_id(node));
	imgui.push_id(str(id(node)));

	imnodes.begin_pin(make_in_pin_id(node), imnodes.PinKind.input);
	imgui.text("(In)");
	imnodes.end_pin();

	imgui.same_line();
	node["face"] = gui.input_sprite("##face", node["face"], (32, 32));
	imgui.same_line();
	has_responses = any(len(edge["text"]) > 0 for edge in node["edges"]);
	imgui.begin_disabled(has_responses);
	node["random"] = gui.input_bool("Random", node["random"]);
	imgui.end_disabled();

	if not dialogue.is_anonymous(node):
		imgui.same_line();
		imgui.text(node["name"]);
		_newline();

	imgui.begin_group();
	for idx in range(len(node["lines"])):
		draw_line(node, idx, edits);
	if imgui.button("New line"):
		node["lines"].append(doc.type_tree.search("lines").inmost.prototype());
	imgui.end_group();
	_newline();

	imgui.begin_group();
	for idx in range(len(node["edges"])):
		draw_edge(node, idx, edits);
	if imgui.button("New edge"):
		node["edges"].append(doc.type_tree.search("edges").inmost.prototype());
	imgui.end_group();
	_newline();

	imgui.pop_id();
	imnodes.end_node();

	for edit in edits:
		edit();

#########################################################
## EDITOR

class DialogueEditor:
	def __init__(self):
		# No settings file: positions live in each node's metadata.aabb, so
		# imnodes has nothing worth persisting and NodeEditor.json is never written.
		config = imnodes.Config();
		config.settings_file = "";
		self.context = imnodes.create_editor(config);
		self.document = AssetManager.get_document("dialogue");
		self.graph = Graph(self.document, None);
		self.layout_pending = False;

		self.clipboard = [];
		self.context_node = None;
		self.rename = gui.RenameModal.for_assets("dialogue", "Rename node");

	def __del__(self):
		imnodes.destroy_editor(self.context);

	def load_root(self, root):
		self.graph = Graph(self.document, root);
		self.layout_pending = never_laid_out(self.graph.get_nodes());

	def place(self, node, position=None):
		if position is None:
			w, h = imnodes.get_screen_size();
			position = imnodes.screen_to_canvas(imgui.ImVec2(w/2, h/2));
		set_position(node, position.x, position.y);
		self.graph.place(node);

	def detach(self, node):
		dialogue.unlink(self.document, node);
		self.graph.remove(node);

	def delete(self, node):
		self.graph.remove(node);
		dialogue.delete(self.document, node);

	def menu_bar(self):
		doc = self.document;
		if imgui.begin_menu_bar():
			if imgui.begin_menu("File"):
				if imgui.menu_item_simple("New source"):
					self.load_root(doc.spawn_entry());
				imgui.end_menu();

			if imgui.begin_menu("Graph"):
				if imgui.begin_menu("Add"):
					if imgui.menu_item_simple("New node", "Cmd+N"):
						self.place(dialogue.spawn_anonymous(doc));
					if imgui.begin_menu("Named node"):
						named = gui.asset_selector("named-node-selector", None, "dialogue", filter=lambda node: not dialogue.is_anonymous(node));
						if named != None:
							self.place(named);
						imgui.end_menu();
					imgui.end_menu();
				if imgui.menu_item_simple("Reflow", enabled=self.graph.root != None):
					self.layout_pending = True;
				imgui.end_menu();

			if imgui.begin_menu("All"):
				clicked = imgui.menu_item_simple("Cull orphans");
				gui.tooltip_warning("Will permanently delete nodes not linked into any graph!");
				if clicked:
					orphans = dialogue.find_orphans(doc);
					for node in orphans:
						self.delete(node);
				imgui.end_menu();
			
			imgui.end_menu_bar();

	def draw_inspector(self):
		root = gui.asset_selector("dialogue-selector", self.graph.root, "dialogue", filter=lambda node: not dialogue.is_anonymous(node));
		if root is not self.graph.root:
			self.load_root(root);

	def handle_shortcuts(self, selected):
		if not imgui.is_window_focused(imgui.WindowFlags_.child_window) or imgui.is_any_item_active():
			return;
		doc = self.document;
		if InputManager.is_command(glfw.KEY_C) and len(selected) > 0:
			self.clipboard = list(selected);
		if InputManager.is_command(glfw.KEY_D):
			for node in selected:
				self.detach(node);
		if InputManager.is_command(glfw.KEY_N):
			self.place(dialogue.spawn_anonymous(doc));
		if InputManager.is_command(glfw.KEY_V):
			for node in self.clipboard:
				self.place(dialogue.spawn_anonymous(doc, node));

	def handle_link_create(self, by_base):
		if not imnodes.begin_create():
			return;
		a = imnodes.PinId();
		b = imnodes.PinId();
		if imnodes.query_new_link(a, b) and a and b:
			ends = [decode_pin(a.id(), by_base), decode_pin(b.id(), by_base)];
			ins = [(node, slot) for node, slot in ends if slot == 0];
			outs = [(node, slot) for node, slot in ends if slot != 0];
			if len(ins) != 1 or len(outs) != 1 or ins[0][0] == None or outs[0][0] == None:
				imnodes.reject_new_item();
			elif imnodes.accept_new_item():
				(src, slot), (dst, _) = outs[0], ins[0];
				src["edges"][slot-1]["node"] = dst["name"];
		imnodes.end_create();

	def handle_link_delete(self, by_base):
		if not imnodes.begin_delete():
			return;
		lid = imnodes.LinkId();
		while imnodes.query_deleted_link(lid):
			if imnodes.accept_deleted_item():
				src, slot = decode_pin(lid.id(), by_base);
				if src != None:
					src["edges"][slot-1]["node"] = "";
		imnodes.end_delete();

	def node_context_menu(self, by_base):
		doc = self.document;
		imnodes.suspend();
		nid = imnodes.NodeId();
		if imnodes.show_node_context_menu(nid):
			self.context_node = by_base.get(nid.id());
			if self.context_node != None:
				imgui.open_popup("node_context_menu");
		node = self.context_node;
		if node != None and imgui.begin_popup("node_context_menu"):
			if imgui.menu_item_simple("Rename"):
				self.rename.begin(node);
			if imgui.menu_item_simple("Duplicate"):
				x0, y0, _, _ = node["metadata"]["aabb"];
				self.place(dialogue.spawn_anonymous(doc, node), imgui.ImVec2(x0 + 32, y0 + 32));
			if imgui.menu_item_simple("Detach", "Cmd+D"):
				self.detach(node);
			if imgui.menu_item_simple("Delete asset"):
				self.delete(node);
			imgui.end_popup();
		imnodes.resume();

	def draw_graph(self):
		doc = self.document;
		nodes = self.graph.get_nodes();
		by_base = {get_base_id(node): node for node in nodes};
		by_name = {node["name"]: node for node in nodes};

		imnodes.begin("graph", imgui.ImVec2(0, 0));

		selected = [by_base[nid.id()] for nid in imnodes.get_selected_nodes() if nid.id() in by_base];
		self.handle_shortcuts(selected);

		for node in nodes:
			push_aabb(node);
			draw_node(node, doc);

		for node in nodes:
			for idx, edge in enumerate(node["edges"]):
				target = by_name.get(edge["node"]);
				if target != None:
					imnodes.link(make_link_id(node, idx), make_out_pin_id(node, idx), make_in_pin_id(target));

		self.handle_link_create(by_base);
		self.handle_link_delete(by_base);
		self.node_context_menu(by_base);

		imnodes.end();

		for node in nodes:
			pull_aabb(node);
		if self.layout_pending and self.graph.root != None:
			dialogue.layout(doc, self.graph.root);
			self.layout_pending = False;

	def draw(self):
		imnodes.set_current_editor(self.context);
		self.menu_bar();

		gui.begin_column("inspector", imgui.get_content_region_avail().x * 0.125);
		self.draw_inspector();
		gui.end_column();

		gui.begin_column("graph");
		self.draw_graph();
		gui.end_column();

		self.rename.draw();
