def reachable(nodes):
	by_name = {node["name"]: node for node in nodes};
	reached = set();
	stack = [node["name"] for node in nodes if not node.get("anonymous", False)];
	while len(stack) > 0:
		name = stack.pop();
		if name in reached or not name in by_name:
			continue;
		reached.add(name);
		stack.extend(edge["node"] for edge in by_name[name]["edges"]);
	return reached;

def find_orphans(nodes):
	reached = reachable(nodes);
	return [node for node in nodes if node.get("anonymous", False) and not node["name"] in reached];
