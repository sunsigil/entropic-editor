from imgui_bundle import imgui, imgui_color_text_edit as te;
import glfw;
import input;
from pathlib import Path;

class TextEditor:
    lua_lang = te.TextEditor.Language.lua()

    def __init__(self):
        self.text_editor = te.TextEditor();
        self.path = None;

    def configure(self, title, text, language=None):
        self.title = str(title);
        self.original = str(text);
    
        self.text_editor = te.TextEditor();
        if language != None:
            self.text_editor.set_language(language);
        self.text_editor.set_text(self.original);
    
    def configure_path(self, path, language=None):
        path = Path(path);
        self.path = path;
        self.configure(path.name, path.read_text(), language);
    
    def get_text(self):
        return self.text_editor.get_text();

    def save(self):
        if self.path != None:
            self.path.write_text(self.get_text());

    def draw(self):
        if self.path != None:
            if imgui.button("Save"):
                self.save();
        self.text_editor.render(self.title);
