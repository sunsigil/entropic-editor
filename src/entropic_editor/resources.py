from pathlib import Path;
import sprites;
import rendering.images as ee_img;

ROOT = Path(__file__).parent / "resources";

# For now, frame counts are hardcoded per known name
# Stupid hack, oh well.
FRAMES = {
	"door": 4,
	"arrow": 5,
	"edit": 1,
};

_sprites = {};
_images = {};

def sprite(name):
	if name not in _sprites:
		_sprites[name] = sprites.Sprite.load(ROOT / f"{name}.png", FRAMES[name]);
	return _sprites[name];

def image(name):
	if name not in _images:
		_images[name] = ee_img.Texture.load(ROOT / f"{name}.png");
	return _images[name];
