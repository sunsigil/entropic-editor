from imgui_bundle import imgui;
from cowtools import foldl;

class Window:
	def __init__(self, instance, gui_id, size):
		self.instance = instance;
		self.gui_id = gui_id;
		self.size = size;

	def __getattr__(self, name):
		return getattr(self.instance, name, None);

class Tool:
	def __init__(self, T, title, size=(720, 720), flags=[], hidden=False, singleton=True):
		self.T = T;

		self.title = title;
		self.size = size;
		self.flags = foldl(lambda a, b : a | b, 0, flags);

		self.hidden = hidden;
		self.singleton = singleton;
	
		self.windows = [];
	
	def window(self, gui_id=None):
		if len(self.windows) > 0:
			if gui_id == None:
				return self.windows[-1];
			else:
				return next((x for x in self.windows if x.gui_id == gui_id), None);
		return None;

	def is_open(self, gui_id=None):
		return self.window(gui_id) != None;

	def open(self, gui_id=None):
		if not (self.singleton and self.is_open(gui_id)):
			window = Window(self.T(), gui_id, self.size);
			self.windows.append(window);
		return self.window(gui_id);

	def close(self):
		self.windows.pop();
	
	def handle_modal_queue(self):
		while len(self.modal_queue) > 0:
			modal_id = self.modal_queue.pop(0);
			imgui.open_popup(modal_id);	

	def draw(self):		
		trash = [];

		for win in self.windows:
			imgui.set_next_window_size(win.size);
			should_close = getattr(win, "should_close") != None and win.should_close();
			_, open = imgui.begin(self.title, not should_close, flags=self.flags);
			win.draw();
			win.size = imgui.get_window_size();
			imgui.end();
			
			if not open:
				trash.append(win);
		
		while len(trash) > 0:
			win = trash.pop();
			self.windows.remove(win);

class ToolWindowRegistry:
	table = {};
	
	def register(tool):
		ToolWindowRegistry.table[tool.T] = tool;
	
	def search(key):
		if key in ToolWindowRegistry.table:
			return ToolWindowRegistry.table[key];

	def all():
		return ToolWindowRegistry.table.values();