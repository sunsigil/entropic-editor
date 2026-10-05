from imgui_bundle import imgui;
from cowtools import foldl;
import itertools;

_uids = itertools.count();

class Panel:
	def __init__(self, title, size=(720, 720), flags=0, key=None):
		self.title = title;
		self.key = key;
		self.uid = next(_uids);
		self.size = imgui.ImVec2(*size) if size != None else None;
		self.flags = flags;

		self.open = True;
		self.focus_pending = False;
		self.focused = False;

		self.result = None;
		self.done = False;
		self.done_frames = 0;

	@property
	def label(self):
		if self.key != None:
			T, ident = self.key;
			return f"{self.title}###{T.__name__}:{ident}";
		return f"{self.title}###panel{self.uid}";

	def close(self):
		self.open = False;

	def focus(self):
		self.focus_pending = True;

	def finish(self, result):
		self.result = result;
		self.done = True;

	def body(self):
		raise NotImplementedError();

	def draw(self):
		if self.size is not None:
			imgui.set_next_window_size(self.size);
		if self.focus_pending:
			imgui.set_next_window_focus();
			self.focus_pending = False;
		_, self.open = imgui.begin(self.label, self.open, flags=self.flags);
		self.focused = imgui.is_window_focused(imgui.FocusedFlags_.root_and_child_windows);
		self.body();
		if self.size is not None:
			self.size = imgui.get_window_size();
		imgui.end();
		return self.open;

class PanelManager:
	panels = [];
	last_focused = None;

	def open(panel):
		PanelManager.panels.append(panel);
		return panel;

	def find(key):
		return next((p for p in PanelManager.panels if p.key == key), None);

	def remove(panel):
		if panel in PanelManager.panels:
			PanelManager.panels.remove(panel);
		if PanelManager.last_focused is panel:
			PanelManager.last_focused = None;

	def any_open():
		return any(p.open and not p.done for p in PanelManager.panels);

	def close_all():
		for panel in PanelManager.panels:
			panel.close();

	def close_last_focused():
		candidates = [p for p in PanelManager.panels if p.open and not p.done];
		if len(candidates) == 0:
			return False;
		target = PanelManager.last_focused if PanelManager.last_focused in candidates else candidates[-1];
		target.close();
		return True;

	def draw_all():
		for panel in list(PanelManager.panels):
			if panel.done:
				panel.done_frames += 1;
				if panel.done_frames > 1:
					PanelManager.remove(panel);
				continue;
			if not panel.draw():
				PanelManager.remove(panel);
			elif panel.focused:
				PanelManager.last_focused = panel;

class ToolPanel(Panel):
	def __init__(self, tool, gui_id):
		super().__init__(tool.title, size=tool.size, flags=tool.flags, key=tool.key(gui_id));
		self.tool = tool;
		self.instance = tool.T();

	def body(self):
		self.instance.draw();
		if self.tool.picker and self.instance.result != None:
			self.finish(self.instance.result);

class Tool:
	def __init__(self, T, title, size=(720, 720), flags=[], hidden=False, picker=False):
		self.T = T;
		self.title = title;
		self.size = size;
		self.flags = foldl(lambda a, b : a | b, 0, flags);
		self.hidden = hidden;
		self.picker = picker;

	def key(self, gui_id=None):
		return (self.T, gui_id);

	def window(self, gui_id=None):
		return PanelManager.find(self.key(gui_id));

	def open(self, gui_id=None):
		existing = self.window(gui_id);
		if existing != None:
			existing.focus();
			return existing;
		return PanelManager.open(ToolPanel(self, gui_id));

class ToolRegistry:
	table = {};

	def register(tool):
		ToolRegistry.table[tool.T] = tool;

	def search(key):
		if key in ToolRegistry.table:
			return ToolRegistry.table[key];

	def all():
		return ToolRegistry.table.values();
