"""information_card.py - A rounded card with a small title, a big value or statement, and a
short explanation. The card slides in, then its text appears one block at a time.

Scene data:  {"tone": "danger", "title": "सावधान", "value": "अनजान लिंक? रुकें!",
              "text": "किसी के कहने पर यूपीआई पिन न डालें।",
              "enter_from": "bottom", "align": "center"}
"""
from __future__ import annotations

from PIL import Image

from src.utils.drawing import text_layer, wrap_text
from src.utils.logger import get_logger
from src.video.gfx.components.base import Component, choice, clean_text
from src.video.gfx.easing import ease, progress
from src.video.gfx.layers import composite, rounded_card
from src.video.gfx.theme import TONES

log = get_logger(__name__)

_FIT_SCALES = (1.0, 0.92, 0.85, 0.78, 0.7, 0.6)
_HEADING_SPACING = 1.38
_BODY_SPACING = 1.45
_SHORT_VALUE_CHARS = 8    # values this short are shown in the big 'value' size


class InformationCard(Component):
    visual_type = "information_card"

    @staticmethod
    def validate(spec: dict) -> dict:
        title = clean_text(spec, "title", 40)
        value = clean_text(spec, "value", 52)
        text = clean_text(spec, "text", 170)
        if not (value or text):
            raise ValueError("an information card needs a 'value' or a 'text'")
        return {
            "tone": choice(spec, "tone", TONES, "cyan"),
            "title": title, "value": value, "text": text,
            "enter_from": choice(spec, "enter_from", ("bottom", "left", "right"), "bottom"),
            "align": choice(spec, "align", ("center", "top"), "center"),
        }

    def __init__(self, theme, spec, box):
        super().__init__(theme, spec, box)
        self.clean = self.validate(spec)
        self._build()

    def _layout(self, scale: float):
        """Create the text pictures at one size. Returns (pieces, card_height)."""
        th, clean = self.theme, self.clean
        pad = th.padding
        strip = th.px(16)
        inner_w = self.w - 2 * pad - strip
        gap = round(pad * 0.4)
        tone = th.tone_color(clean["tone"])
        pieces: list[tuple] = []   # (order, picture, dx, dy, x_in_card, y_in_card)
        y = 0

        def add_block(order, text, font, size, color, spacing):
            nonlocal y
            if not text:
                return
            if pieces:
                y += gap
            for line in wrap_text(text, font, inner_w):
                layer, (dx, dy) = text_layer(line, font, color)
                pieces.append((order, layer, dx, dy, pad + strip, y))
                y += round(size * spacing)

        add_block(0, clean["title"], th.font("heading", "title", scale),
                  th.size("title", scale), tone, _HEADING_SPACING)
        big = len(clean["value"]) <= _SHORT_VALUE_CHARS
        value_key = "value" if big else "subheading"
        add_block(1, clean["value"], th.font("heading", value_key, scale),
                  th.size(value_key, scale), th.color("text"), _HEADING_SPACING)
        add_block(2, clean["text"], th.font("body", "body", scale),
                  th.size("body", scale), th.color("text_secondary"), _BODY_SPACING)
        return pieces, y + 2 * pad

    def _build(self) -> None:
        th = self.theme
        for scale in _FIT_SCALES:   # use the biggest text size where the card fits its box
            pieces, card_h = self._layout(scale)
            if card_h <= self.h:
                break
        else:
            log.warning("Card does not fit its box even at the smallest size: %s", self.clean)
        self.fit_scale, self.card_height = scale, card_h
        self._pieces = pieces

        tone = th.tone_color(self.clean["tone"])
        border = tuple(round(a + (b - a) * 0.55) for a, b in zip(th.color("card_border"), tone))
        self._card, self._margin = rounded_card(th, self.w, card_h, th.color("card"), border, accent=tone)
        self._card_y = self.y + (0 if self.clean["align"] == "top" else (self.h - card_h) / 2)

    def draw(self, frame: Image.Image, t: float, duration: float) -> None:
        th = self.theme
        p = ease("out_cubic", progress(t, 0.0, th.reveal))
        shift = (1 - p) * th.slide
        dx = {"left": -shift * 2, "right": shift * 2}.get(self.clean["enter_from"], 0)
        dy = shift if self.clean["enter_from"] == "bottom" else 0
        fade = ease("out_quad", progress(t, 0.0, th.fade))
        composite(frame, self._card, self.x - self._margin + dx, self._card_y - self._margin + dy,
                  alpha=fade, scale=0.94 + 0.06 * p)

        for order, layer, pdx, pdy, px, py in self._pieces:
            appear = ease(th.ease_name, progress(t, th.reveal * 0.45 + order * th.stagger, th.fade))
            composite(frame, layer, self.x + px - pdx + dx, self._card_y + py - pdy + dy + (1 - appear) * th.slide * 0.15,
                      alpha=appear)