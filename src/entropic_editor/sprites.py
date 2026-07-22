from PIL import Image;
from pathlib import Path;

from assets import *;
from cowtools import *;
import editor_gui as gui;
from imgui_bundle import imgui;
from pathlib import Path;
import context;
from enum import Enum;

def _is_image_black(img):
	pixels = img.load();
	black = 0;
	non_black = 0;
	for y in range(img.height):
		for x in range(img.width):
			p = pixels[x, y];
			if p[3] >= 128 and p[0] > 32 or p[1] > 32 or p[2] > 32:
				non_black += 1;
			else:
				black += 1;
	ratio = non_black / black if black > 0 else math.inf;
	return ratio <= 0.01;

def _invert_black(img):
	pixels = img.load();
	inversion = [];
	result = Image.new(img.mode, img.size);
	for y in range(img.height):
		for x in range(img.width):
			p = pixels[x, y];
			r = 255 - p[0];
			g = 255 - p[1];
			b = 255 - p[2];
			a = p[3];
			inversion.append((r, g, b, a));
	result.putdata(inversion);
	return result;

class EditorSprite:
	def _cut_frame(self, i):
		box = (0, i * self.frame_height, self.raw_width, (i+1) * self.frame_height);
		return self.raw_image.crop(box);

	def __init__(self, path, frames):
		self.path = Path(path);
		self.raw_image = Image.open(self.path);
		self.raw_width = self.raw_image.width;
		self.raw_height = self.raw_image.height;

		self.frame_count = max(frames, 1);
		self.frame_width = self.raw_width;
		self.frame_height = self.raw_height // self.frame_count;
		self.frame_images = [self._cut_frame(i) for i in range(self.frame_count)];
		self.frame_textures = [make_texture(frame.tobytes(), frame.width, frame.height) for frame in self.frame_images];

		self.preview_width = self.raw_width * self.frame_count;
		self.preview_height = self.frame_height;
		self.preview_image = Image.new("RGBA", (self.preview_width, self.preview_height));
		for (idx, frame) in enumerate(self.frame_images):
			if _is_image_black(self.raw_image):
				frame = _invert_black(frame);
			xy = (idx * self.frame_width, 0);
			self.preview_image.paste(frame, xy);
		self.preview_texture = make_texture(self.preview_image.tobytes(), self.preview_width, self.preview_height);

class SpriteBank:
	by_resource = {};
	by_name = {};

	def update(name, path, frames):
		index = (path, frames);
		if not index in SpriteBank.by_resource:
			path = Path(path);
			if path.exists() and path.is_file():
				SpriteBank.by_resource[index] = EditorSprite(path, frames);
			else:
				return;
		SpriteBank.by_name[name] = index;
	
	def	refresh():
		sprites = AssetManager.get_all("sprite");
		for sprite in sprites:
			name = sprite["name"];
			relative_path = sprite["path"];
			real_path = AssetManager.get_document("sprite").directory / relative_path;
			frames = sprite["frames"];
			SpriteBank.update(name, real_path, frames);
	
	def search(name, path=None, frames=None, safe=True):
		if path != None:
			path = AssetManager.get_document("sprite").directory / path;

		if name != None and name in SpriteBank.by_name:
			return SpriteBank.by_resource[SpriteBank.by_name[name]];
	
		if path != None and frames != None and (path, frames) in SpriteBank.by_resource:
			return SpriteBank.by_resource[(path, frames)];
		if path != None:
			for key in SpriteBank.by_resource:
				if key[0] == path:
					return SpriteBank.by_resource[key];
	
		if safe:
			return SpriteBank.search("null");
		return None;

	def is_image_used(path):
		for p,f in SpriteBank.by_resource:
			if p == path:
				return True;
		return False;

class SpritePreview:
	def draw(name, path=None, frames=None, **kwargs):
		sprite = SpriteBank.search(name, path, frames);
		imgui.image(imgui.ImTextureRef(sprite.preview_texture), imgui.ImVec2(sprite.preview_width * 2, sprite.preview_height * 2));
		if "show_dimensions" in kwargs and kwargs["show_dimensions"]:
			imgui.text(f"{sprite.frame_width}x{sprite.frame_height}");

	def draw_thumbnail(key, size):
		sprite = SpriteBank.search(key);
		aspect = sprite.frame_width / sprite.frame_height;
		imgui.image(imgui.ImTextureRef(sprite.frame_textures[0]), imgui.ImVec2(aspect * size, size));

class SpriteImporter:
	class Pattern:
		class Op(Enum):
			UNION = 0
			INTERSECT = 1
			COMPLEMENT = 2
		def __init__(self, glob, op):
			self.glob = glob;
			self.op = op;

		def is_valid(self):
			return isinstance(self.glob, str) and len(self.glob) > 0;

		def filter(self, root, acc):
			matches = list(root.glob(self.glob));
			match self.op:
				case SpriteImporter.Pattern.Op.UNION:
					return acc + matches;
				case SpriteImporter.Pattern.Op.INTERSECT:
					return [x for x in acc if x in matches];
				case SpriteImporter.Pattern.Op.COMPLEMENT:
					return [x for x in acc if not x in matches];
			
	def __init__(self):
		self.root = context.get().game_directory/"assets/sprites/new";
		self.patterns = [];
		self.modes = ["mass", "individual"];
		self.mode = self.modes[0];
	
	def get_candidates(self):
		candidates = list(self.root.glob(str("**/*.png")));
		candidates = list(filter(lambda x: not SpriteBank.is_image_used(x), candidates));
		for pattern in self.patterns:
			if not pattern.is_valid():
				print("Invalid");
				continue;
			candidates = pattern.filter(self.root, candidates);
		return sorted(list(set(candidates)));

	def import_path(self, path):
		sprite = AssetManager.get_document("sprite").spawn_entry();
		path = path.relative_to(AssetManager.get_document("sprite").directory);
		sprite["path"] = str(path);
		sprite["name"] = "_".join(path.parts);
	
	def draw(self):
		if imgui.collapsing_header("Globs"):
			for (idx,pattern) in enumerate(self.patterns):
				imgui.text(f"Filter {idx}");
				imgui.same_line();
				pattern.glob = gui.input_string(f"##glob_{idx}", pattern.glob);
				imgui.same_line();
				pattern.op = gui.input_enum(f"##op_{idx}", pattern.op, SpriteImporter.Pattern.Op);
			if imgui.button("Add glob"):
				self.patterns.append(SpriteImporter.Pattern("", SpriteImporter.Pattern.Op.UNION));

		if imgui.collapsing_header("List"):
			self.mode = gui.input_enum("Import mode", self.mode, self.modes);

			candidates = self.get_candidates();
			for candidate in candidates:
				imgui.text(str(candidate.relative_to(self.root)));
				if self.mode == "individual":
					imgui.same_line();
					if imgui.button(f"Import##{candidate}"):
						self.import_path(candidate);

			if self.mode == "mass":
				if imgui.button("Import all"):
					candidates = self.get_candidates();
					for candidate in candidates:
						self.import_path(candidate);
			
			