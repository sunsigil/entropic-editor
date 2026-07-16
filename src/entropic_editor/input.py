from imgui_bundle import imgui;
import glfw;

class InputManager:
	_glfw_handle = None;
	_imgui_impl = None;

	_glfw_io = {};
	_imgui_io = None;

	_scroll_dx = None;
	_scroll_dy = None;

	def _scroll_callback(handle, dx, dy):
		InputManager._scroll_dx = dx;
		InputManager._scroll_dy = dy;

	def initialize(glfw_handle, imgui_impl):
		InputManager._glfw_handle = glfw_handle;
		InputManager._imgui_impl = imgui_impl;
		InputManager._imgui_io = imgui.get_io();
		InputManager._glfw_io = {};
	
		glfw.set_scroll_callback(InputManager._glfw_handle, InputManager._scroll_callback);

	def update():
		for key in range(glfw.KEY_SPACE, glfw.KEY_LAST+1):
			if not key in InputManager._glfw_io:
				InputManager._glfw_io[key] = [glfw.get_key(InputManager._glfw_handle, key), False];
			else:
				InputManager._glfw_io[key] = [glfw.get_key(InputManager._glfw_handle, key), InputManager._glfw_io[key][0]];
		for key in range(glfw.MOUSE_BUTTON_1, glfw.MOUSE_BUTTON_LAST+1):
			if not key in InputManager._glfw_io:
				InputManager._glfw_io[key] = [glfw.get_mouse_button(InputManager._glfw_handle, key), False];
			else:
				InputManager._glfw_io[key] = [glfw.get_mouse_button(InputManager._glfw_handle, key), InputManager._glfw_io[key][0]];

	def get_imgui_cursor():
		return InputManager._imgui_io.mouse_pos;

	def is_held(key):
		return InputManager._glfw_io[key][0];

	def is_pressed(key):
		return InputManager._glfw_io[key][0] and not InputManager._glfw_io[key][1];

	def is_released(key):
		return InputManager._glfw_io[key][1] and not InputManager._glfw_io[key][0];

	def is_command(keys):
		if not InputManager.is_held(glfw.KEY_LEFT_SUPER):
			return;
		if isinstance(keys, list):
			for idx, key in enumerate(keys):
				if idx == len(keys)-1:
					if not InputManager.is_pressed(key):
						return False;
				else:
					if not InputManager.is_held(key):
						return False;
		if not InputManager.is_pressed(keys):
			return False;
		return True;

	def get_scroll_offset():
		return (InputManager._scroll_dx, InputManager._scroll_dy);