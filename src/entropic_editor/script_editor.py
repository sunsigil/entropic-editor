from imgui_bundle import imgui, imgui_color_text_edit as te;
import glfw;
import input;

class ScriptEditor:
	def __init__(self):	
		self.text_editor = te.TextEditor();
	
	def configure(self, title, text, language=None):
		self.title = str(title);
		self.original = str(text);
	
		self.text_editor = te.TextEditor();
		if language != None:
			self.text_editor.set_language(language);
		self.text_editor.set_text(self.original);
	
	def get_text(self):
		return self.text_editor.get_text();
	
	def draw(self):
		self.text_editor.render(self.title);
			
