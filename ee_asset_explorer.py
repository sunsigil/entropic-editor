from imgui_bundle import imgui;
from ee_assets import AssetManager;
from ee_sprites import SpritePreview, SpriteBank;
import math;

class AssetExplorer:
	def __init__(self):
		self.target = None;
		self.result = None;
		self.search = "";
	
	def configure(self, target, type):
		self.target = target;
		self.type = type;
	
	def _is_private(self, x):
		asset = AssetManager.search(self.type, x);
		return "private" in asset and asset["private"];

	def draw(self):
		listings = [s["name"] for s in AssetManager.get_all(self.type)];

		_, self.search = imgui.input_text("Search", self.search);
		if len(self.search) > 0:
			listings = list(filter(lambda x: self.search in x, listings));
		
		listings = [x for x in listings if not self._is_private(x)];

		listings.sort();
		
		wdw_w = imgui.get_content_region_avail().x/1.25;
		sprite_w = 64;
		cols = int(wdw_w // sprite_w);
		rows = int(math.ceil(len(listings) / cols));
	
		i = 0;
		for r in range(rows):
			for c in range(cols):
				if i < len(listings):
					imgui.begin_group();

					asset = AssetManager.search(self.type, listings[i]);
					sprite_name = listings[i] if self.type == "sprite" else (asset["sprite"] if "sprite" in asset else "");
					sprite = SpriteBank.search(sprite_name);

					if imgui.image_button(f"##{id(i)}", imgui.ImTextureRef(sprite.frame_textures[0]), imgui.ImVec2(64, 64)):
						self.result = listings[i];
					imgui.text(listings[i][:min(10, len(listings[i]))]);

					imgui.end_group();
					imgui.same_line();
				i += 1;
			imgui.new_line();
		
	def is_targeting(self, target):
		return target == self.target;

	def should_close(self):
		return self.result != None;
		
	def get_result(self):
		return self.result;