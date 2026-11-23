"""title_reveal.py - A large heading that rises into place line by line, with an optional
small label above it and an accent underline that sweeps under highlighted words.

Scene data:  {"title": "UPI पेमेंट कैसे काम करता है?", "kicker": "डिजिटल समझ",
              "highlight": ["UPI"], "tone": "cyan", "align": "center"}
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from src.utils.drawing import font_ascent, text_layer
from src.utils.logger import get_logger
from src.video.gfx.components.base import (Component, as_word_list, choice, clean_text,
                                           normalize_word, wrap_words)
from src.video.gfx.easing import ease, progress
from src.video.gfx.layers import composite, rounded_rect_sprite
from src.video.gfx.theme import TONES

log = get_logger(__name__)

_FIT_SCALES = (1.0, 0.9, 0.8, 0.7, 0.6)
_LINE_SPACING = 1.38   # Hindi needs more room than English for vowel signs above and below


@dataclass
class _Word:
    layer: Image.Image
    dx: int
    dy: int
    x: float
    width: float
    bar: Image.Image | None


class TitleReveal(Component):
    visual_type = "title_reveal"

    @staticmethod
    def validate(spec: dict) -> dict:
        return {
            "title": clean_text(spec, "title", 80, required=True),
            "kicker": clean_text(spec, "kicker", 40),
            "highlight": as_word_list(spec.get("highlight")),
            "tone": choice(spec, "tone", TONES, "cyan"),
            "align": choice(spec, "align", ("center", "left"), "center"),
        }

    def __init__(self, theme, spec, box):
        super().__init__(theme, spec, box)
        self.clean = self.validate(spec)
        self._build()

    def _build(self) -> None:
        th = self.theme
        clean = self.clean
        words = clean["title"].split()
        accent = th.tone_color(clean["tone"])
        highlight = {normalize_word(word) for word in clean["highlight"]}

        # Find the biggest text size where everything fits inside the box
        for scale in _FIT_SCALES:
            font = th.font("heading", "heading", scale)
            lines = wrap_words(words, font, self.w)
            size = th.size("heading", scale)
            line_h = round(size * _LINE_SPACING)
            kicker_h = round(th.size("small", scale) * 1.9) if clean["kicker"] else 0
            if kicker_h + len(lines) * line_h <= self.h:
                break
        else:
            log.warning("Title does not fit its box even at the smallest size: %s", clean["title"])
        self.fit_scale = scale

        block_h = kicker_h + len(lines) * line_h
        top = self.y + (self.h - block_h) / 2
        space = font.getlength(" ")
        ascent = font_ascent(font)
        bar_h = max(6, round(size * 0.09))

        self._kicker = None
        if clean["kicker"]:
            small = th.font("body", "small", scale)
            layer, (dx, dy) = text_layer(clean["kicker"], small, th.color("text_secondary"))
            width = small.getlength(clean["kicker"])
            x = self.x + (self.w - width) / 2 if clean["align"] == "center" else self.x
            self._kicker = (layer, dx, dy, x, top)

        self._lines = []
        for index, line in enumerate(lines):
            widths = [font.getlength(word) for word in line]
            line_w = sum(widths) + space * (len(line) - 1)
            x = self.x + (self.w - line_w) / 2 if clean["align"] == "center" else self.x
            y = top + kicker_h + index * line_h
            items = []
            for word, width in zip(line, widths):
                marked = normalize_word(word) in highlight
                layer, (dx, dy) = text_layer(word, font, accent if marked else th.color("text"))
                bar = rounded_rect_sprite(th, width, bar_h, bar_h // 2, accent) if marked else None
                items.append(_Word(layer, dx, dy, x, width, bar))
                x += width + space
            bar_y = min(y + ascent + size * 0.18, y + line_h - bar_h)
            self._lines.append({"y": y, "bar_y": bar_y, "items": items, "delay": 0.12 + index * th.stagger})

    def draw(self, frame: Image.Image, t: float, duration: float) -> None:
        th = self.theme
        if self._kicker is not None:
            layer, dx, dy, x, y = self._kicker
            p = ease("out_cubic", progress(t, 0.0, th.fade))
            composite(frame, layer, x - dx, y - dy + (1 - p) * th.slide * 0.25, alpha=p)

        for line in self._lines:
            p = ease(th.ease_name, progress(t, line["delay"], th.reveal))
            lift = (1 - p) * th.slide * 0.35
            for item in line["items"]:
                composite(frame, item.layer, item.x - item.dx, line["y"] - item.dy + lift, alpha=p)
            sweep = ease("in_out_cubic", progress(t, line["delay"] + th.reveal * 0.7, 0.5))
            if sweep > 0:
                for item in line["items"]:
                    if item.bar is not None:
                        part = item.bar.crop((0, 0, max(1, int(item.bar.width * sweep)), item.bar.height))
                        composite(frame, part, item.x, line["bar_y"] + lift, alpha=p)