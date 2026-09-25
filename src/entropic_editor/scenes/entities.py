from assets import AssetManager;
from sprites import SpriteBank;

def get_sprite(entity):
	prototype = AssetManager.search("prototype", entity["prototype"]);
	if prototype == None:
		return None;
	return SpriteBank.search(prototype["sprite"], safe=False);

def get_aabb(entity):
	x, y = entity["position"];

	prototype = AssetManager.search("prototype", entity["prototype"]);
	if prototype != None:
		sprite = SpriteBank.search(prototype["sprite"], safe=False);
		if sprite != None:
			dx, dy = prototype["sprite_offset"];
			return [x+dx, y+dy, x+dx+sprite.frame_width, y+dy+sprite.frame_height];
	
		if prototype["has_blocker"]:
			x0, y0, x1, y1 = prototype["blocker"];
			return [x+x0, y+y0, x+x1, y+y1];
		elif prototype["has_trigger"]:
			x0, y0, x1, y1 = prototype["trigger"];
			return [x+x0, y+y0, x+x1, y+y1];

	return [x-8, y-8, x+8, y+8];

def get_body_key(entity):
	"""Where this sits in the draw order. Sorting and picking share it so they
	can't drift apart. Entities all live on layer 0."""
	return (0, 0, get_depth(entity));

def get_depth(entity):
	prototype = AssetManager.search("prototype", entity["prototype"]);
	y_offset = prototype["y_sort_offset"] if prototype != None else 0;
	return get_aabb(entity)[3] + y_offset;

def spawn(scene, prototype_name, position):
	entity = AssetManager.get_tree("scene").search("entities").inmost.prototype();
	entity["name"] = "";
	entity["position"] = [int(position[0]), int(position[1])];
	entity["prototype"] = prototype_name;
	scene["entities"].append(entity);
	return entity;
