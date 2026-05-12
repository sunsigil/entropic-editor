from imgui_bundle import imgui;
import json;
import difflib;
import glfw;

from ee_cowtools import *;
import ee_context;
from ee_input import InputManager;

class NoticeEditor:
	def __init__(self):
		file = open(ee_context.env["game_path"]/"data/notices.json", "r+");
		json_data = json.load(file);
		file.close();
		
		self.tags = [];
		self.strings = json_data;
		for string in self.strings:
			for tag in string["tags"]:
				if not tag in self.tags:
					self.tags.append(tag);
	
		self.new_string = "";
		self.new_tag = "";
		self.focus = None;
	
	def enumify(self, text):
		text = text.upper();
		text = text.replace(" ", "_");
		return text;
	
	def add_tag(self, string):
		if len(self.new_tag) == 0:
			return;

		self.new_tag = self.enumify(self.new_tag.strip());

		if self.new_tag not in string["tags"]:
			string["tags"].append(self.new_tag);
		if self.new_tag not in self.tags:
			self.tags.append(self.new_tag);
		
		self.new_tag = "";
	
	def remove_tag(self, string, tag):
		string["tags"] = [t for t in string["tags"] if t != tag];
		for s in self.strings:
			if tag in s["tags"]:
				return;
		self.tags.remove(tag);
	
	def change_focus(self, focus):
		old_focus = self.focus;
		self.focus = focus;
		if self.focus != old_focus:
			self.new_string = "";
			self.new_tag = "";
	
	def save(self):
		file = open(ee_context.env["game_path"]/"data/notices.json", "w");
		file.seek(0);
		file.truncate();
		file.write(json.dumps(self.strings, indent=4));
		file.close();

	def draw(self):
		if imgui.begin_tab_bar("Tabs"):
			if imgui.begin_tab_item("Strings")[0]:

				for i in range(len(self.strings)):
					string = self.strings[i];
					
					imgui.set_next_item_open(self.focus == string);
					if imgui.tree_node(f"{string["string"]}####{id(string)}"):
						imgui.push_id(str(id(string)));
						self.change_focus(string);

						_, string["string"] = imgui.input_text_multiline(f"##string_{i}", string["string"]);
						if imgui.collapsing_header("Tags"):
							trash = [];
							for tag in string["tags"]:
								imgui.text(tag);
								imgui.same_line();
								if imgui.button(f"x##{tag}"):
									trash.append(tag);
							for tag in trash:
								self.remove_tag(string, tag);
							
							hints = difflib.get_close_matches(self.enumify(self.new_tag).lstrip(), self.tags);
							for hint in hints:
								if hint not in string["tags"] and imgui.button(hint):
									self.new_tag = hint;
									self.add_tag(string);
								imgui.same_line();
							if len(hints) > 0:
								imgui.new_line();
							_, self.new_tag = imgui.input_text("##new_tag", self.new_tag);
							imgui.same_line();
							if imgui.button("Add tag"):
								self.add_tag(string);
						
						imgui.pop_id();
						imgui.tree_pop();

				imgui.separator_text("");

				_, self.new_string = imgui.input_text_multiline("##new_string", self.new_string);
				imgui.same_line();
				if imgui.button("Add string") and len(self.new_string) > 0:
					self.strings.append(
						{
							"string" : self.new_string,
							"tags" : []	
						}
					);
					self.new_string = "";

				imgui.end_tab_item();
			
			if imgui.begin_tab_item("Tags")[0]:
				for tag in self.tags:
					imgui.text(f"{tag} ({len([s for s in self.strings if tag in s["tags"]])})");
				imgui.end_tab_item();

			imgui.end_tab_bar();

			if InputManager.is_held(glfw.KEY_LEFT_SUPER) and InputManager.is_pressed(glfw.KEY_S):
				self.save();
	
	def on_close(self):
		self.save();