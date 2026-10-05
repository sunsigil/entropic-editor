from pathlib import Path, PurePosixPath;

_editor_root = None;
_game_root = None;

def configure(editor_root, game_root):
	global _editor_root, _game_root;
	_editor_root = Path(editor_root).absolute();
	_game_root = Path(game_root).absolute();

def editor_root():
	if _editor_root == None:
		raise RuntimeError("paths.configure() has not been called");
	return _editor_root;

def game_root():
	if _game_root == None:
		raise RuntimeError("paths.configure() has not been called");
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
