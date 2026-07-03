from imgui_bundle import imgui;
from assets import AssetManager;
from sprites import SpritePreview, SpriteBank;
import math;
import string;
from editor_gui import *;

class GlyphExplorer:
	def __init__(self):
		self.sprite = SpriteBank.search("glyph");
		self.filters = {
			"lowercase": lambda x: x.islower(),
			"uppercase": lambda x: x.isupper(),
			"numerals": lambda x: x.isnumeric(),
			"punctuation": lambda x: x in string.punctuation,
			"special": lambda x: ord(x) < 32
		};
		self.formats = {
			"lowercase": lambda x: f"\'{x}\'",
			"uppercase": lambda x: f"\'{x}\'",
			"numerals": lambda x: f"\'{x}\'",
			"punctuation": lambda x: f"\'{x}\'",
			"special": lambda x: f"\\x{format(ord(x), "X")}"
		}
		self.key = list(self.filters.keys())[0];

	def draw(self):
		begin_column("filter_window", imgui.get_content_region_avail().x * 0.15);
		for filter in self.filters:
			if imgui.menu_item(filter, "", p_selected = self.key == filter)[0]:
				self.key = filter;
		end_column();

		begin_column("glyph_window");
		count = 0;
		for i in range(0, 128):
			if self.filters[self.key](str(chr(i))):
				imgui.image(imgui.ImTextureRef(self.sprite.frame_textures[i]), imgui.ImVec2(24, 24));
				if imgui.is_item_hovered():
					imgui.set_tooltip(self.formats[self.key](str(chr(i))));
				imgui.same_line();
				count += 1;
				if count >= 16:
					imgui.new_line();
					count = 0;
		imgui.new_line();
		end_column();