from PIL import Image, ImageDraw, ImageOps;
import OpenGL.GL as gl;
from cowtools import *;

def make_texture(buffer, width, height):
    texture = gl.glGenTextures(1);
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture);
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST);
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST);
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, buffer);
    return texture;

def scale_dimensions(width, height, sx, sy):
    return max(round(width * sx), 1), max(round(height * sy), 1)

class Texture:
    def __init__(self, source):
        self.handle = None;
        if isinstance(source, Texture):
            source = source.source;

        self.source = source.convert("RGBA");
        self.handle = make_texture(self.source.tobytes(), self.width, self.height);
        self.draw = ImageDraw.Draw(self.source);
        
        self.dirty = False;

    def __del__(self):
        if self.handle is None:
            return;
        try:
            gl.glDeleteTextures(1, [self.handle]);
        except Exception:
            pass;
    
    @classmethod
    def empty(cls, width, height):
        source = Image.new("RGBA", (width, height), (0, 0, 0, 0));
        return cls(source);
    
    @classmethod
    def load(cls, path):
        source = Image.open(path);
        texture = cls(source);
        source.close();
        return texture;
    
    @classmethod
    def scale(cls, texture, sx, sy):
        w, h = scale_dimensions(texture.width, texture.height, sx, sy);
        source = texture.source.resize((w, h), Image.Resampling.NEAREST);
        return cls(source);
    
    @classmethod
    def invert(cls, texture):
        alpha = texture.source;
        alpha = alpha.getchannel("A");
        
        rgb = texture.source;
        rgb = rgb.convert("RGB");
        rgb = ImageOps.invert(rgb);
        
        rgb.putalpha(alpha);
        return cls(rgb);

    @property
    def width(self):
        return self.source.width;
    @property
    def height(self):
        return self.source.height;

    def refresh(self):
        if not self.dirty:
            return;
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.handle);
        gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0, self.width, self.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, self.source.tobytes());
        self.dirty = False;

    def resize(self, width, height):
        self.source = self.source.crop((0, 0, width, height));
        self.draw = ImageDraw.Draw(self.source);
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.handle);
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, self.width, self.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, self.source.tobytes());
        self.dirty = False;

    def export(self, path):
        self.source.save(path);

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
        self.source.paste(to_paste, point, mask=image);
        self.dirty = True;

