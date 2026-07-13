from PIL import Image;
from pathlib import Path;

from assets import *;
from cowtools import *;
import editor_gui as gui;
from imgui_bundle import imgui;
from pathlib import Path;
import context;

def _is_image_black(img):
	pixels = img.load();
	for y in range(img.height):
		for x in range(img.width):
			p = pixels[x, y];
			if p[3] >= 128 and p[0] > 16 or p[1] > 16 or p[2] > 16:
				return False;
	return True;

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

		if _is_image_black(self.raw_image):
			self.raw_image = _invert_black(self.raw_image);

		self.frame_count = max(frames, 1);
		self.frame_width = self.raw_width;
		self.frame_height = self.raw_height // self.frame_count;
		self.frame_images = [self._cut_frame(i) for i in range(self.frame_count)];
		self.frame_textures = [make_texture(frame.tobytes(), frame.width, frame.height) for frame in self.frame_images];

		self.preview_width = self.raw_width * self.frame_count;
		self.preview_height = self.frame_height;
		self.preview_image = Image.new("RGBA", (self.preview_width, self.preview_height));
		for (idx, frame) in enumerate(self.frame_images):
			xy = (idx * self.frame_width, 0);
			self.preview_image.paste(frame, xy);
		self.preview_texture = make_texture(self.preview_image.tobytes(), self.preview_width, self.preview_height);

class SpriteBank:
	entries = {};

	def _update(name, path, frames):
		real_path = AssetManager.get_document("sprite").directory / path;
		editor_sprite = EditorSprite(real_path, frames);
		SpriteBank.entries[name] = editor_sprite;
		SpriteBank.entries[path] = editor_sprite;
	
	def update():
		sprites = AssetManager.get_all("sprite");

		for sprite in sprites:

			name = sprite["name"];
			asset_path = sprite["path"];
			real_path = AssetManager.get_document("sprite").directory / asset_path;
			frames = sprite["frames"] if "frames" in sprite else 1;

			if name not in SpriteBank.entries or frames != SpriteBank.entries[name].frame_count or real_path != SpriteBank.entries[name].path:
				if Path.is_file(real_path):
					SpriteBank._update(name, asset_path, frames);
				else:
					SpriteBank._update(name, "null.png", 1);
	
	def search(name, path=None, frames=None, safe=True):
		if not name in SpriteBank.entries:
			if path != None and frames != None:
				SpriteBank._update(name, path, frames);
			else:
				SpriteBank.update();
		if not name in SpriteBank.entries:
			if safe:
				return SpriteBank.entries["null.png"];
			return None;
		return SpriteBank.entries[name];

class SpritePreview:
	def draw(name, path=None, frames=None, **kwargs):
		sprite = SpriteBank.search(name, path, frames);
		imgui.image(imgui.ImTextureRef(sprite.preview_texture), imgui.ImVec2(sprite.preview_width * 2, sprite.preview_height * 2));
		if "show_dimensions" in kwargs and kwargs["show_dimensions"]:
			imgui.text(f"{sprite.frame_width}x{sprite.frame_height}");

	def draw_thumbnail(name, size):
		sprite = SpriteBank.search(name);
		aspect = sprite.frame_width / sprite.frame_height;
		imgui.image(imgui.ImTextureRef(sprite.frame_textures[0]), imgui.ImVec2(aspect * size, size));

class SpriteImporter:
	def __init__(self):
		self.root = context.get().game_directory/"assets/sprites";
		self.pattern = None;

		self.candidates = [];
	
	def get_candidates(self):
		self.candidates = [];
		for entry in self.root.glob(self.pattern):
			self.candidates.append(entry.relative_to(self.root));
	
	def draw(self):
		self.pattern = gui.input_string("Glob", self.pattern);

		if imgui.button("Preview"):
			self.get_candidates();
		imgui.same_line();
		if imgui.button("Import"):
			self.get_candidates();
			for path in self.candidates:
				sprite = AssetManager.get_document("sprite").spawn_entry();
				sprite["path"] = str(path);
				sprite["name"] = "_".join(path.parts);

		if self.candidates != None:
			for path in self.candidates:
				imgui.text(str(path));