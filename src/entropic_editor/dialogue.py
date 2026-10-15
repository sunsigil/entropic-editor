# EDITS

def spawn_anonymous(doc, source=None):
	new = doc.spawn_entry(source);
	new["name"] = f"_{id(new)}";
	new["metadata"]["anonymous"] = True;
	return new;

def unlink(doc, node):
	for other in doc.instances:
		for edge in other["edges"]:
			if edge["node"] == node["name"]:
				edge["node"] = "";

def delete(doc, node):
	unlink(doc, node);
	doc.delete_entry(node);

# QUERIES

def is_anonymous(node):
	return node["metadata"]["anonymous"];

# Queries take either an AssetDocument or a plain list of instances, so the
# game's generators can call them on raw JSON without loading a document.
def _instances(source):
	if source == None:
		return [];
	if isinstance(source, list):
		return source;
	return source.instances;

def reachable_from(doc, roots):
	nodes = _instances(doc);
	by_name = {node["name"]: node for node in nodes};
	reached = [];
	seen = set();
	stack = [root for root in roots if root != None];
	while len(stack) > 0:
		node = stack.pop();
		if id(node) in seen:
			continue;
		seen.add(id(node));
		reached.append(node);
		for edge in node["edges"]:
			target = by_name.get(edge["node"]);
			if target != None:
				stack.append(target);
	return reached;

def reachable(doc):
	nodes = _instances(doc);
	named = [node for node in nodes if not is_anonymous(node)];
	return reachable_from(nodes, named);

def find_orphans(doc):
	nodes = _instances(doc);
	reached = {id(node) for node in reachable(nodes)};
	return [node for node in nodes if is_anonymous(node) and id(node) not in reached];

# LAYOUT
#
# Positions each node in the DFS tree under `root` by writing the min corner
# of its metadata.aabb, keeping its size. Sizes come from the aabb too, so
# this runs anywhere; the editor refreshes sizes from imnodes every frame.

def layout(doc, root, gap=64):
	by_name = {node["name"]: node for node in doc.instances};
	visited = set();

	def visit(node, x, y0):
		visited.add(id(node));
		x0, y0_old, x1, y1 = node["metadata"]["aabb"];
		w, h = x1 - x0, y1 - y0_old;
		node["metadata"]["aabb"] = [x, y0, x + w, y0 + h];
		y = y0;
		for edge in node["edges"]:
			child = by_name.get(edge["node"]);
			if child != None and id(child) not in visited:
				visit(child, x + w + gap, y);
				y += h + gap;

	if root != None:
		visit(root, 0, 0);
