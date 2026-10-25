# Loads a game project the way the editor does, so generators and tools see
# the same documents, types and paths. The typefile lives at assets/types.json.

from pathlib import Path, PurePosixPath;

import asset_types;
from assets import AssetManager, is_asset_document;

_editor_root = None;
_game_root = None;

def editor_root():
	if _editor_root == None:
		raise RuntimeError("project.load() has not been called");
	return _editor_root;

def game_root():
	if _game_root == None:
		raise RuntimeError("project.load() has not been called");
	return _game_root;

def is_stored(value):
	if not isinstance(value, str) or len(value) == 0:
		return False;
	if "\\" in value:
		return False;
	parts = PurePosixPath(value).parts;
	if PurePosixPath(value).is_absolute() or ".." in parts:
		return False;
	return True;

def resolve(stored):
	return game_root() / PurePosixPath(stored);

def relativize(absolute):
	return Path(absolute).absolute().relative_to(game_root()).as_posix();

def load(root):
	global _editor_root, _game_root;
	_editor_root = Path(__file__).parent.absolute();
	_game_root = Path(root).absolute();
	root = _game_root;

	typefile = root / "assets/types.json";
	if typefile.is_file():
		asset_types.load_typefile(typefile);

	for path in sorted((root / "assets").rglob("*.json")):
		if is_asset_document(path):
			AssetManager.load_document(path);

	return AssetManager;
