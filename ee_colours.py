import numpy as np;
import math;

def RGB8882RGB565(c):
	r, g, b = c[:3];
	r = round((r / 255) * 31);
	g = round((g / 255) * 63);
	b = round((b / 255) * 31);
	return (r << 11) | (g << 5) | b;

def RGB5652888(c):
	r = (c & 0b1111100000000000) >> 11;
	g = (c & 0b0000011111100000) >> 5;
	b = c & 0b0000000000011111;
	r = round(r / 31 * 255);
	g = round(g / 63 * 255);
	b = round(b / 31 * 255);
	return r, g, b;

def RGB2LAB(c):
	r, g, b = c[:3];
	rn, gn, bn = r/255, g/255, b/255;
	rl = ((rn + 0.055) / 1.055)**2.4 if rn > 0.04045 else rn/12.92;
	gl = ((gn + 0.055) / 1.055)**2.4 if gn > 0.04045 else gn/12.92;
	bl = ((bn + 0.055) / 1.055)**2.4 if bn > 0.04045 else bn/12.92;
	Mxyz = np.array([
		[0.4124564, 0.3575761, 0.1804375],
		[0.2126729, 0.7151522, 0.0721750],
		[0.0193339, 0.1191920, 0.9503041]
	]);
	x, y, z = Mxyz @ np.array([[rl], [gl], [bl]]);
	xn = 0.95047;
	yn = 1.0;
	zn = 1.08883;
	def f(t):
		return t ** (1/3) if t > 0.008856 else 7.787 * t + (16/116);
	l = 116 * f(y/yn) - 16;
	a = 500 * (f(x/xn) - f(y/yn));
	b = 200 * (f(y/yn) - f(z/zn));
	return l, a, b;

def TRANSRGB888():
	return (255, 0, 255);
def TRANSRGB565():
	return 0b1111100000011111;

def pixel_preprocess(c):
	r, g, b = c[:3];
	if len(c) >= 4: 
		a = c[3];
		if a < 255:
			return TRANSRGB888();

	r = round(r / 255 * 31);
	g = round(g / 255 * 63);
	b = round(b / 255 * 31);
	r = round(r / 31 * 255);
	g = round(g / 63 * 255);
	b = round(b / 31 * 255);

	return r, g, b;

def restrict_precision(c):
	r, g, b = c[:3];
	r = round((r / 255) * 31);
	g = round((g / 255) * 63);
	b = round((b / 255) * 31);
	r = round((r / 31) * 255);
	g = round((g / 63) * 255);
	b = round((b / 31) * 255);
	return (r, g, b);

def apply_gamma(c):
	r, g, b = c[:3];
	Gr, Gg, Gb = 1.2, 1.2, 1.6;
	rf, gf, bf = r/255, g/255, b/255;
	rf, gf, bf = rf ** (1/Gr), gf ** (1/Gg), bf ** (1/Gb);
	return (int(rf*255), int(gf*255), int(bf*255));

def hue(c):
	r, g, b = c[:3];
	r /= 255;
	g /= 255;
	b /= 255;

	lmax = max(r, g, b);
	lmin = min(r, g, b);
	range = lmax-lmin;
	if range <= 0:
		return 0;
	
	if r >= g and r >= b:
		return (g-b)/range;
	if g >= r and g >= b:
		return 2 + (b-r)/range;
	if b >= r and b >= g:
		return 4 + (r-g)/range;

def saturation(c):
	c = c[:3];
	m = min(c);
	M = max(c);
	return (M-m) / M if M != 0 else 0;

def value(c):
	r, g, b = c[:3];
	return math.sqrt(0.299*r**2 + 0.587*g**2 + 0.114*b**2);