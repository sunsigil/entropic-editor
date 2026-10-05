from pathlib import Path, PurePosixPath;

def editor_root():
	import context;
	return Path(context.get().editor_directory);

def game_root():
	import context;
	return Path(context.get().game_directory);

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
