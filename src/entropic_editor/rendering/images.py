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

        self.dirty = False;

    def resize(self, width, height):
       pass; 

    def refresh(self, force=False):
        if not self.dirty:
            return;
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture);
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, self.width, self.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, self.image.tobytes());
        self.dirty = False;
            
    def export(self, path):
        self.image.save(path);

    def clear(self, colour):
        self.draw.rectangle((0, 0, self.width, self.height), fill=colour);
        self.dirty = True;

    def draw_pixel(self, point, colour):
        self.draw.point(point, fill=colour);
        self.dirty = True;
    
    def draw_rectangle(self, rect, colour, fill=False):
        self.draw.rectangle(rect, outline=colour, fill=colour if fill else None);
        self.dirty = True;

    def draw_line(self, start, end, colour):
        x0, y0 = start;
        x1, y1 = end;
        self.draw.line((x0, y0, x1, y1), fill=colour);
        self.dirty = True;

    def draw_circle(self, center, radius, colour, fill=False):
        self.draw.circle(center, radius, outline=colour, fill=colour if fill else None);
        self.dirty = True;
    
    def draw_image(self, point, image, colour=None):
        to_paste = colour if colour != None else image;
        self.image.paste(to_paste, point, mask=image);
        self.dirty = True;

