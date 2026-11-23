"""text_engine.py - Draws text with proper shaping, so Hindi (Devanagari) letters join correctly.

Why this exists: Pillow's pip package for Windows cannot shape complex scripts, so Hindi
shows unjoined letters and misplaced vowel signs. This module uses HarfBuzz (uharfbuzz)
to decide WHICH glyphs to draw and WHERE, and FreeType (freetype-py) to draw them.
Both install with pip on Windows and Linux.

Use:
    font = HarfBuzzFont("assets/fonts/Hind-Bold.ttf", 72)
    width = font.getlength("स्कैम")
    font.draw_text(image, (x, y), "स्कैम", fill=(255, 255, 255), anchor="lm",
                   stroke_width=4, stroke_fill=(0, 0, 0))
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import freetype
import uharfbuzz as hb
from PIL import Image, ImageChops
from src.utils.drawing import layer_from_masks

_DEVANAGARI_RANGES = ((0x0900, 0x097F), (0xA8E0, 0xA8FF))
_CACHE_LIMIT = 512  # how many shaped texts to remember per font


def _is_devanagari(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in _DEVANAGARI_RANGES)


def split_runs(text: str) -> list[tuple[str, str]]:
    """Split text into runs that must be shaped separately, e.g. 'UPI स्कैम' ->
    [('Latn', 'UPI '), ('Deva', 'स्कैम')].

    HarfBuzz must be told the script of each run. If Latin and Devanagari were shaped
    together, the Hindi part would be shaped wrongly. Spaces, digits and punctuation
    join the run before them.
    """
    runs: list[list[str]] = []
    leading = ""  # neutral characters at the very start, added to the first run
    for char in text:
        if _is_devanagari(char):
            script = "Deva"
        elif char.isalpha():
            script = "Latn"
        else:
            script = None  # space, digit, punctuation, joiner
        if script is None:
            if runs:
                runs[-1][1] += char
            else:
                leading += char
        elif runs and runs[-1][0] == script:
            runs[-1][1] += char
        else:
            runs.append([script, leading + char])
            leading = ""
    if not runs and leading:
        return [("Latn", leading)]
    return [(script, run) for script, run in runs]


def _outline(mask: Image.Image, radius: int) -> Image.Image:
    """Grow a mask outwards by `radius` pixels (with rounded corners) to make a text outline."""
    result = mask.copy()
    steps = max(8, radius * 4)
    rings = [radius] if radius <= 2 else [radius, radius / 2]
    for ring in rings:
        for i in range(steps):
            angle = 2 * math.pi * i / steps
            dx, dy = round(ring * math.cos(angle)), round(ring * math.sin(angle))
            if dx or dy:
                result = ImageChops.lighter(result, ImageChops.offset(mask, dx, dy))
    return result


class HarfBuzzFont:
    """One font at one size. Offers getlength() and draw_text()."""

    def __init__(self, path: str | Path, size: int):
        self.path = str(path)
        self.size = int(size)
        if not Path(self.path).is_file():
            raise FileNotFoundError(f"Font file not found: {self.path}")

        # HarfBuzz works in 26.6 fixed point: scale = size * 64 means positions come back as pixels * 64
        self._hb_font = hb.Font(hb.Face(hb.Blob.from_file_path(self.path)))
        self._hb_font.scale = (self.size * 64, self.size * 64)

        self._ft_face = freetype.Face(self.path)
        self._ft_face.set_pixel_sizes(0, self.size)
        self.ascent = self._ft_face.size.ascender / 64          # pixels above the baseline
        self.descent = -self._ft_face.size.descender / 64       # pixels below the baseline

        self._layouts: dict = {}
        self._masks: dict = {}

    # ---------- shaping and drawing glyphs ----------
    def _layout(self, text: str):
        """Shape the text. Returns (glyphs, advance).

        glyphs  = list of (glyph picture, x, y): the pen starts at x=0, y is measured
                  downwards from the baseline.
        advance = total width of the text in pixels.
        """
        if text in self._layouts:
            return self._layouts[text]
        if len(self._layouts) > _CACHE_LIMIT:
            self._layouts.clear()

        pen_x = 0.0
        glyphs = []
        for script, run in split_runs(text):
            buffer = hb.Buffer()
            buffer.add_str(run)
            buffer.direction = "ltr"
            buffer.script = script
            buffer.language = "hi" if script == "Deva" else "en"
            hb.shape(self._hb_font, buffer, {"kern": True, "liga": True})

            for info, position in zip(buffer.glyph_infos, buffer.glyph_positions):
                # after shaping, 'codepoint' is the glyph number inside the font
                self._ft_face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
                slot = self._ft_face.glyph
                bitmap = slot.bitmap
                if bitmap.width and bitmap.rows:
                    picture = Image.frombytes(
                        "L", (bitmap.width, bitmap.rows), bytes(bitmap.buffer), "raw", "L", bitmap.pitch
                    )
                    x = round(pen_x + position.x_offset / 64 + slot.bitmap_left)
                    y = round(-position.y_offset / 64 - slot.bitmap_top)
                    glyphs.append((picture, x, y))
                pen_x += position.x_advance / 64

        self._layouts[text] = (glyphs, pen_x)
        return self._layouts[text]

    def _make_masks(self, text: str, stroke_width: int):
        """Build the text as a greyscale mask (and an outline mask). Cached, since captions repeat."""
        key = (text, stroke_width)
        if key in self._masks:
            return self._masks[key]
        if len(self._masks) > _CACHE_LIMIT:
            self._masks.clear()

        glyphs, advance = self._layout(text)
        pad = stroke_width + 2
        if glyphs:
            left = min(x for _, x, _ in glyphs)
            top = min(y for _, _, y in glyphs)
            right = max(x + picture.width for picture, x, _ in glyphs)
            bottom = max(y + picture.height for picture, _, y in glyphs)
        else:
            left = top = right = bottom = 0

        mask = Image.new("L", (right - left + 2 * pad, bottom - top + 2 * pad), 0)
        for picture, x, y in glyphs:
            cx, cy = x - left + pad, y - top + pad
            box = (cx, cy, cx + picture.width, cy + picture.height)
            # 'lighter' merges overlapping glyphs (vowel signs overlap letters) without darkening edges
            mask.paste(ImageChops.lighter(mask.crop(box), picture), (cx, cy))

        origin = (pad - left, pad - top)  # where the pen start (on the baseline) sits inside the mask
        outline = _outline(mask, stroke_width) if stroke_width > 0 else None
        self._masks[key] = (mask, outline, origin, advance)
        return self._masks[key]

    # ---------- public methods ----------
    def getlength(self, text: str) -> float:
        """Width of the text in pixels (same name Pillow's fonts use)."""
        return self._layout(text)[1]

    def render_layer(self, text: str, fill, stroke_width: int = 0, stroke_fill=(0, 0, 0)):
        """Make a transparent RGBA picture of the text.

        Returns (picture, (dx, dy)). To put the text's top-left corner (anchor 'la') at (x, y),
        paste the picture at (x - dx, y - dy).
        """
        if not text.strip():
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), (0, 0)
        mask, outline, origin, _ = self._make_masks(text, int(stroke_width))
        layer = layer_from_masks(mask, outline, fill, stroke_fill)
        return layer, (origin[0], origin[1] - round(self.ascent))
    
    def draw_text(
        self,
        image: Image.Image,
        xy: tuple[float, float],
        text: str,
        fill,
        anchor: str = "la",
        stroke_width: int = 0,
        stroke_fill=(0, 0, 0),
    ) -> None:
        """Draw text onto an RGB image.

        anchor = two letters like Pillow: horizontal l/m/r (left, middle, right) and
        vertical a/t (top), m (middle), s (baseline), b/d (bottom).
        """
        if not text.strip():
            return
        mask, outline, origin, advance = self._make_masks(text, int(stroke_width))
        x, y = xy
        horizontal, vertical = (anchor + "la")[0], (anchor + "la")[1]
        if horizontal == "m":
            x -= advance / 2
        elif horizontal == "r":
            x -= advance

        if vertical in ("a", "t"):
            baseline = y + self.ascent
        elif vertical == "m":
            baseline = y + (self.ascent - self.descent) / 2
        elif vertical in ("b", "d"):
            baseline = y - self.descent
        else:  # 's'
            baseline = y

        left = round(x) - origin[0]
        top = round(baseline) - origin[1]
        box = (left, top, left + mask.width, top + mask.height)
        if outline is not None:
            image.paste(stroke_fill, box, outline)
        image.paste(fill, box, mask)


@lru_cache(maxsize=64)
def get_harfbuzz_font(path: str, size: int) -> HarfBuzzFont:
    """Load a font once per (file, size) and reuse it."""
    return HarfBuzzFont(path, size)