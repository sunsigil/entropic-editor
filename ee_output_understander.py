from imgui_bundle import imgui;
import json;
from pathlib import Path;
from serial import Serial;
from enum import Enum;

from ee_cowtools import *;
from ee_canvas import Canvas;

class OutputUnderstander:
	class BufferState(Enum):
		DORMANT = 0,
		RECORDING = 1,
		READY = 2

	def __init__(self):
		self.platform = None;
		self.device_path = None;
		self.device = None;

		self.buffer = bytearray();
		self.buffer_state = OutputUnderstander.BufferState.DORMANT;
		self.json_object = None;
		self.error_log = [];
	
		self.touch_canvas = Canvas(240, 320, 0.5);
	
	def read(self):
		waiting = self.device.in_waiting;

		if waiting > 0:
			bytes = self.device.read(max(1, min(2048, waiting)));
			
			if bytes[0] == 0x2 and self.buffer_state == OutputUnderstander.BufferState.DORMANT:
				bytes = bytes[1:];
				self.buffer_state = OutputUnderstander.BufferState.RECORDING;

			if self.buffer_state == OutputUnderstander.BufferState.RECORDING:
				self.buffer += bytes;
				if self.buffer[-3:] == b"\x03\r\n":
					self.buffer = self.buffer[:-3];
					self.buffer_state = OutputUnderstander.BufferState.READY;

		return waiting;
	
	def draw_uptime(self):
		if imgui.collapsing_header("TIME"):
			imgui.text(f"Device online for {self.json_object["uptime"]} seconds");
	
	def draw_button_mask(self):
		if imgui.collapsing_header("BUTTONS"):
			mask = self.json_object["button_mask"];
			names = ["START", "SELECT", "A", "B", "DOWN", "RIGHT", "LEFT", "UP"];
			bits = [int((mask & 1 << i) > 0) for i in range(16)];
			for idx, bit in enumerate(bits):
				if idx < len(names):
					imgui.text(f"[{names[idx]}] " if bit > 0 else f"{names[idx]} ");
					imgui.same_line();
			imgui.new_line();
	
	def draw_touch(self):
		if imgui.collapsing_header("TOUCH"):
			imgui.begin_group();
			self.touch_canvas.clear((0, 0, 0));
			touch = self.json_object["touch"];
			if touch["pressure"] > 0:
				self.touch_canvas.draw_circle(touch["x"], touch["y"], 4, (255, 255, 255));
			self.touch_canvas.render();
			imgui.end_group();
			imgui.same_line();
			if touch["pressure"] > 0:
				imgui.text(f"({touch["x"]}, {touch["y"]})");
			else:
				imgui.text("Not currently touching");

	def draw(self):
		if self.platform == None:
			imgui.text("Select platform:");
			self.platform = imgui_selector(id(self.platform), ["RP2350"], self.platform);
		elif self.device_path == None:
			imgui.text("Select device:");
			all_devices = [x for x in Path("/dev").iterdir() if "usbmodem" in str(x)];
			self.device_path = imgui_selector(id(self.device_path), all_devices, self.device_path, lambda x: "None" if x == None else x.name);
		elif self.device == None:
			self.device = Serial(str(self.device_path), 115200);
		else:
			self.read();
			if self.buffer_state == OutputUnderstander.BufferState.READY:
				try:
					json_string = self.buffer.decode().strip();
					self.json_object = json.loads(json_string);
				except Exception as e:
					self.error_log.append(e);
					self.error_log.append(self.buffer.decode());
					if len(self.error_log) > 100:
						self.error_log.pop(0);
				self.buffer.clear();
				self.buffer_state = OutputUnderstander.BufferState.DORMANT;
			
			if imgui.begin_tab_bar("Tabs"):
				if self.json_object != None:
					if imgui.begin_tab_item("Data")[0]:
						if "uptime" in self.json_object:
							self.draw_uptime();
						if "button_mask" in self.json_object:
							self.draw_button_mask();
						if "touch" in self.json_object:
							self.draw_touch();
						imgui.end_tab_item();
				if imgui.begin_tab_item("Raw")[0]:
					imgui.text(json.dumps(self.json_object, indent=4));
					imgui.end_tab_item();
				if imgui.begin_tab_item("Error Log")[0]:
					for e in self.error_log:
						imgui.text(str(e));
					imgui.end_tab_item();
				imgui.end_tab_bar();

					

