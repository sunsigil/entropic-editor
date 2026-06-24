import OpenGL;
OpenGL.FULL_LOGGING = True;
from OpenGL.GL import *;

import glfw;

from imgui_bundle import imgui;
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer;

__context = None;

def glfw_error_callback(error, description):
 		print(f"[GLFW] {error}: {description}");

def get_clipboard_text(_ctx: imgui.internal.Context) -> str:
	s = glfw.get_clipboard_string(__context.glfw_handle);
	return s.decode();
def set_clipboard_text(_ctx: imgui.internal.Context, text: str) -> str:
	glfw.set_clipboard_string(__context.glfw_handle, text);

class Context:
	def __init__(self, directory, name, width, height):
		self.directory = directory;
		
		self.name = name;
		self.width = width;
		self.height = height;

		glfw.set_error_callback(glfw_error_callback);
		if not glfw.init():
			print("Failed to initialize GLFW. Exiting");
			exit();
		glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3);
		glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3);
		glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE);
		glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE);
		self.glfw_handle = glfw.create_window(self.width, self.height, self.name, None, None);
		if not self.glfw_handle:
			print("Failed to create window. Exiting");
			glfw.terminate();
			exit();
		glfw.make_context_current(self.glfw_handle);

		print("Renderer:", glGetString(GL_RENDERER).decode("utf-8"));
		print("GL Version:", glGetString(GL_VERSION).decode("utf-8"));
		print("SL Version:", glGetString(GL_SHADING_LANGUAGE_VERSION).decode("utf-8"));

		imgui.create_context();
		self.imgui_io = imgui.get_io();
		self.imgui_io.config_windows_move_from_title_bar_only = True;
		imgui.style_colors_dark()
		self.imgui_impl = GlfwRenderer(self.glfw_handle);

		platform_io = imgui.get_platform_io();
		platform_io.platform_get_clipboard_text_fn = get_clipboard_text;
		platform_io.platform_set_clipboard_text_fn = set_clipboard_text;

		self.time = glfw.get_time();
		self.delta_time = 0;

	def __del__(self):
		self.imgui_impl.shutdown();
		imgui.destroy_context();

		glfw.destroy_window(self.glfw_handle);
		glfw.terminate();

	def is_alive(self):
		return not glfw.window_should_close(self.glfw_handle);
	
	def begin_frame(self):
		time_last = self.time;
		self.time = glfw.get_time();
		self.delta_time = self.time - time_last;

		glfw.poll_events();
		self.imgui_impl.process_inputs();

		glEnable(GL_PROGRAM_POINT_SIZE);
		glClearColor(0, 0, 0, 1);
		glClear(GL_COLOR_BUFFER_BIT);

		imgui.new_frame();

	def end_frame(self):
		imgui.render();
		self.imgui_impl.render(imgui.get_draw_data());
		imgui.end_frame();
		glfw.swap_buffers(self.glfw_handle);

def get():
	global __context;
	return __context;
def set(c):
	global __context;
	__context = c;