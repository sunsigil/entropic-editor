from imgui_bundle import imgui;
import qrcode;
import base64;
import re;

from cowtools import *;
from assets import *;
from canvas import Canvas;

class EnDeCoder:
	def __init__(self):
		self.qr_data = "";
		self.qr_code = None;
		self.qr_canvas = None;
		self.qr_path = "";

		self.b64_byte_list = "";
		self.b64_bytes = bytes();
		self.b64_string = "";
	
	def draw(self):
		if imgui.begin_tab_bar("Formats"):
			if imgui.begin_tab_item("QR")[0]:
				_, self.qr_data = imgui.input_text("Data", self.qr_data);
				imgui.same_line();
				if imgui.button("Encode"):
					self.qr_code = qrcode.make(self.qr_data).get_image().convert("RGBA");
					self.qr_canvas = Canvas(self.qr_code.width, self.qr_code.height);
				
				if self.qr_code != None:
					self.qr_canvas.clear((0, 0, 0, 0));
					self.qr_canvas.draw_image(0, 0, self.qr_code);
					self.qr_canvas.render();

					_, self.qr_path = imgui.input_text("Path", self.qr_path);
					imgui.same_line();
					if imgui.button("Save"):
						self.qr_code.save(self.qr_path);
				imgui.end_tab_item();
			
			if imgui.begin_tab_item("Base64")[0]:
				_, self.b64_byte_list = imgui.input_text("##encode", self.b64_byte_list);
				imgui.same_line();
				if imgui.button("Encode"):
					try:
						tokens = re.split(r",| ", self.b64_byte_list);
						tokens = [t for t in tokens if len(t) > 0];
						self.b64_bytes = bytes([int(t, 16) for t in tokens]);
						self.b64_string = base64.b64encode(self.b64_bytes).decode("utf-8");
					except:
						self.b64_string = "";
				
				_, self.b64_string = imgui.input_text("##decode", self.b64_string);
				imgui.same_line();
				if imgui.button("Decode"):
					try:
						self.b64_bytes = base64.b64decode(self.b64_string);
						byte_list = list(self.b64_bytes);
						self.b64_byte_list = ", ".join([str(hex(b)) for b in byte_list]);
					except Exception as e:
						print(e);
						self.b64_byte_list = "";
				imgui.end_tab_item();
			imgui.end_tab_bar();
					

