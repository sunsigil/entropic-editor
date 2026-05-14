from imgui_bundle import imgui;
from ee_assets import AssetManager;
from ee_canvas import Canvas;
from ee_sprites import SpriteBank;
import ee_context;
from ee_imgui import *;
from ee_tool_window import ToolWindowRegistry;
from ee_sprite_explorer import SpriteExplorer;
from PIL import Image;

class AnimationViewer:
	def __init__(self):
		self.canvas = Canvas(240, 128, 2);
		self.scale = 240 / self.canvas.height;

		self.sprite = AssetManager.get_assets("sprite")[0];
		self.frame = 0;
		
		self.animate = True;
		self.show_AABB = False;
		self.timer = 0;

		self.force_looping_rules = False;
		self.scale = 1;

	def draw(self):
		preview = SpriteBank.get(self.sprite["name"]);
		frames = list(reversed(preview.frame_images)) if self.sprite["reverse"] else list(preview.frame_images);
		self.frame = min(max(self.frame, 0), len(frames));

		self.canvas.clear((128, 128, 128));
		draw_x = self.canvas.width/2;
		draw_y = self.canvas.height/2;
		self.canvas.draw_image(draw_x, draw_y, frames[self.frame]);
		if self.show_AABB:
			self.canvas.draw_aabb((draw_x, draw_y, draw_x+preview.frame_width, draw_y+preview.frame_height), (255, 0, 0));
		self.canvas.render();

		if preview.frame_count > 1:	
			animate_changed, self.animate = imgui.checkbox("Animate", self.animate);
			if animate_changed:
				self.frame = 0;
			if self.animate:
				self.timer += ee_context.delta_time;
				if self.timer >= 0.2:
					self.timer = 0;
					self.frame += 1;
					if self.frame >= preview.frame_count:
						self.frame = 0;
			else:
				_, self.frame = imgui.slider_int("Frame", self.frame, 0, preview.frame_count-1);
		
		_, self.show_AABB = imgui.checkbox("Show AABB", self.show_AABB);

		self.sprite = imgui_asset_selector(id(self), "sprite", self.sprite);
		imgui.same_line();
		spexp = ToolWindowRegistry.lookup(SpriteExplorer);
		if imgui.button(f"...##{id(self)}") and not spexp.is_open():
			spexp.open();
			spexp.get().configure(self);
		if spexp.is_open() and spexp.get().is_targeting(self):
			harvest = spexp.get_result();
			self.sprite = AssetManager.search("sprite", harvest) if harvest != None else self.sprite;
		
		if imgui.button("Save as GIF"):
			save_frames = list(frames);
			for (idx, frame) in enumerate(save_frames):
				w, h = frame.size;
				save_frames[idx] = frame.resize((w*self.scale, h*self.scale), Image.NEAREST);
			start = save_frames[0];
			start.save(
				f"{self.sprite["name"]}.gif", append_images=save_frames[1:], save_all=True,
				duration=200, disposal=2, loop=(0 if not self.force_looping_rules else (0 if self.sprite["loop"] else None))
			);
		imgui.same_line();
		_, self.force_looping_rules = imgui.checkbox("Force looping rules", self.force_looping_rules);
		imgui.same_line();
		_, self.scale = imgui.input_int("Scale", self.scale);