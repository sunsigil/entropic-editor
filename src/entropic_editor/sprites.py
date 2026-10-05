from PIL import Image, ImageStat; 
from pathlib import Path;

from assets import *;
from cowtools import *;
import editor_gui as gui;
from imgui_bundle import imgui;
from pathlib import Path;
import context;
from enum import Enum;
import math;
import rendering.images as ee_img;
import paths;

class Sprite:
    def _compute_is_dark(self, img_thresh=0.05, px_thresh=32):
        alpha = self.sheet;
        alpha = alpha.getchannel("A");
        alpha = alpha.point(lambda x: 255 if x >= 255 else 0);
        alpha = alpha.convert("1");
        
        lum = self.sheet;
        lum = lum.convert("L");
        lum = lum.point(lambda x: 255 if x > px_thresh else 0);

        stat = ImageStat.Stat(lum, mask=alpha);
        bright_fraction = stat.mean[0] / 255;
        return stat.count[0] > 0 and bright_fraction < img_thresh;

    def __init__(self, sheet, frame_count):
        self.sheet = sheet.convert("RGBA");
        self.frame_count = clamp(frame_count, 1, sheet.height);

        self.sheet_width = self.sheet.width;
        self.sheet_height = self.sheet.height;
        
        self.width = self.sheet.width;
        self.height = self.sheet.height // self.frame_count;
            
        def cut_frame(i):
            box = (0, i * self.height, self.width, (i+1) * self.height);
            return ee_img.Texture(self.sheet.crop(box));
        self.frames = [cut_frame(i) for i in range(self.frame_count)];

        self.thumbnail_cache = {};
        self.is_dark = self._compute_is_dark();

    @classmethod
    def load(cls, path, frame_count):
        with Image.open(path) as sheet:
            return cls(sheet, frame_count);

    def thumbnail(self, frame_idx=0, width=None, height=None, invert_dark=False):
        image = self.frames[frame_idx];
        width = width if width else image.width;
        height = height if height else image.height;

        w_ratio = width / image.width;
        h_ratio = height / image.height;
        scale = min(w_ratio, h_ratio);
        out_w, out_h = ee_img.scale_dimensions(image.width, image.height, scale, scale);
        
        invert = invert_dark and self.is_dark;
        key = (frame_idx, out_w, out_h, invert);
        if key in self.thumbnail_cache:
            return self.thumbnail_cache[key];

        pic = ee_img.Texture.scale(image, scale, scale);
        if invert:
            pic = ee_img.Texture.invert(pic);
        self.thumbnail_cache[key] = pic;
        return pic;

class SpriteBank:
    by_resource = {};
    by_name = {};
    mtimes = {};

    def update(name, path, frames):
        path = Path(path);
        index = (path, frames);
        try:
            mtime = path.stat().st_mtime_ns;
        except OSError:
            return False;

        if SpriteBank.mtimes.get(index) != mtime:
            SpriteBank.mtimes[index] = mtime;
            try:
                SpriteBank.by_resource[index] = Sprite.load(path, frames);
            except Exception as error:
                print(f"Failed to load sprite '{name}' from {path}: {error}");

        if not index in SpriteBank.by_resource:
            return False;
        SpriteBank.by_name[name] = index;
        return True;
    
    def refresh():
        wanted_names = set();
        wanted_resources = set();
        for sprite in AssetManager.get_all("sprite"):
            name = sprite["name"];
            path = paths.resolve(sprite["path"]);
            frames = sprite["frames"];
            if SpriteBank.update(name, path, frames):
                wanted_names.add(name);
                wanted_resources.add((path, frames));

        for name in list(SpriteBank.by_name):
            if not name in wanted_names:
                del SpriteBank.by_name[name];
        for index in list(SpriteBank.by_resource):
            if not index in wanted_resources:
                del SpriteBank.by_resource[index];
        for index in list(SpriteBank.mtimes):
            if not index in wanted_resources:
                del SpriteBank.mtimes[index];
    
    def search(name, path=None, frames=None, safe=True):
        if path != None:
            path = paths.resolve(path);

        if name != None and name in SpriteBank.by_name:
            return SpriteBank.by_resource[SpriteBank.by_name[name]];
    
        if path != None and frames != None and (path, frames) in SpriteBank.by_resource:
            return SpriteBank.by_resource[(path, frames)];
        if path != None:
            for key in SpriteBank.by_resource:
                if key[0] == path:
                    return SpriteBank.by_resource[key];
    
        if safe:
            return SpriteBank.search("null");
        return None;

    def is_image_used(path):
        for p,f in SpriteBank.by_resource:
            if p == path:
                return True;
        return False;

class SpriteImporter:
    class Pattern:
        class Op(Enum):
            UNION = 0
            INTERSECT = 1
            COMPLEMENT = 2
        def __init__(self, glob, op):
            self.glob = glob;
            self.op = op;

        def is_valid(self):
            return isinstance(self.glob, str) and len(self.glob) > 0;

        def filter(self, root, acc):
            matches = list(root.glob(self.glob));
            match self.op:
                case SpriteImporter.Pattern.Op.UNION:
                    return acc + matches;
                case SpriteImporter.Pattern.Op.INTERSECT:
                    return [x for x in acc if x in matches];
                case SpriteImporter.Pattern.Op.COMPLEMENT:
                    return [x for x in acc if not x in matches];
            
    def __init__(self):
        self.root = paths.resolve("assets/sprites/new");
        self.patterns = [];
        self.modes = ["mass", "individual"];
        self.mode = self.modes[0];
    
    def get_candidates(self):
        candidates = list(self.root.glob(str("**/*.png")));
        candidates = list(filter(lambda x: not SpriteBank.is_image_used(x), candidates));
        for pattern in self.patterns:
            if not pattern.is_valid():
                print("Invalid");
                continue;
            candidates = pattern.filter(self.root, candidates);
        return sorted(list(set(candidates)));

    def import_path(self, path):
        sprite = AssetManager.get_document("sprite").spawn_entry();
        sprite["path"] = paths.relativize(path);
        path = path.relative_to(self.root.parent);
        parts = list(path.parts[:-1]) + [path.stem];
        sprite["name"] = "_".join(parts);
    
    def draw(self):
        if imgui.collapsing_header("Globs"):
            for (idx,pattern) in enumerate(self.patterns):
                imgui.text(f"Filter {idx}");
                imgui.same_line();
                pattern.glob = gui.input_string(f"##glob_{idx}", pattern.glob);
                imgui.same_line();
                pattern.op = gui.input_enum(f"##op_{idx}", pattern.op, SpriteImporter.Pattern.Op);
            if imgui.button("Add glob"):
                self.patterns.append(SpriteImporter.Pattern("", SpriteImporter.Pattern.Op.UNION));

        if imgui.collapsing_header("List"):
            self.mode = gui.input_enum("Import mode", self.mode, self.modes);

            candidates = self.get_candidates();
            for candidate in candidates:
                imgui.text(str(candidate.relative_to(self.root)));
                if self.mode == "individual":
                    imgui.same_line();
                    if imgui.button(f"Import##{candidate}"):
                        self.import_path(candidate);

            if self.mode == "mass":
                if imgui.button("Import all"):
                    candidates = self.get_candidates();
                    for candidate in candidates:
                        self.import_path(candidate);
            
            
