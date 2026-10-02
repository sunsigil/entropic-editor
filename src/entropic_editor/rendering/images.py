from PIL import Image, ImageDraw;
import OpenGL.GL as gl;

def make_texture(buffer, width, height):
    texture = gl.glGenTextures(1);
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture);
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST);
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST);
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buffer);
    return texture;

class Surface:
    def __init__(self, width, height):
        self.width = width;
        self.height = height;

        self.image = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0));
        self.texture = make_texture(self.image.tobytes(), width, height);
        self.draw = ImageDraw.Draw(self.image);

        self.dirty_rectangles = [];

    def clear(self, colour):
        self.draw.rectangle((0, 0, self.width, self.height), fill=colour);

    def draw_pixel(self, point, colour):
        self.draw.point(point, fill=colour);
    
    def draw_rectangle(self, rect, colour, fill=False):
        self.draw.rectangle(rect, outline=colour, fill=colour if fill else None);

    def draw_line(self, start, end, colour):
        x0, y0 = start;
        x1, y1 = end;
        self.draw.line((x0, y0, x1, y1), fill=colour);

    def draw_circle(self, center, radius, colour, fill=False):
        self.draw.circle(center, radius, outline=colour, fill=colour if fill else None);
    
    def draw_image(self, point, image, colour=None):
        to_paste = colour if colour != None else image;
        self.image.paste(to_paste, point, mask=image);

    def refresh(self, force=False):
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture);
        
        if force:
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, self.width, self.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, self.image.tobytes());
            self.dirty_rectangles.clear();
            return;

        def refresh_region(rect):
            x0, y0, x1, y1 = rect;
            w, h = x1 - x0, y1 - y0;
            gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, x0, y0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, self.image.crop(rect).tobytes());
        while len(self.dirty_rectangles) > 0:
            rect = self.dirty_rectangles.pop();
            refresh_region(rect);
