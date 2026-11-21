"""captions.py - Groups spoken words into short caption lines and draws them.

Settings come from style.yaml (captions.*). Word timings come from the voice step,
so each caption appears exactly when it's spoken.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass

from PIL import ImageDraw

from src.config_loader import Config
from src.models import WordTiming
from src.utils.drawing import get_font, hex_to_rgb

_SENTENCE_END = (".", "!", "?")
_POSITIONS = {"top": 0.14, "center": 0.50, "lower_third": 0.72}  # fraction of screen height
_POP_SECONDS = 0.12


def _normalize(word: str) -> str:
    """Lowercase and strip punctuation so 'Iran,' matches 'iran'."""
    return re.sub(r"[^a-z0-9']", "", word.lower())


@dataclass
class CaptionChunk:
    words: list[WordTiming]
    start: float
    end: float


def build_chunks(words: list[WordTiming], words_per_line: int) -> list[CaptionChunk]:
    """Split words into short groups. A sentence ending also ends the group."""
    groups: list[list[WordTiming]] = []
    current: list[WordTiming] = []
    for word in words:
        current.append(word)
        if len(current) >= words_per_line or word.text.endswith(_SENTENCE_END):
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    chunks = []
    for i, group in enumerate(groups):
        # A caption stays until the next one starts, so the screen never flickers empty
        end = groups[i + 1][0].start if i + 1 < len(groups) else group[-1].end + 0.3
        chunks.append(CaptionChunk(words=group, start=group[0].start, end=end))
    return chunks


class CaptionRenderer:
    def __init__(self, cfg: Config, words: list[WordTiming], highlight_words: list[str], size: tuple[int, int]):
        self.width, self.height = size
        self.enabled = cfg.style_value("captions.enabled", True)
        self.font_path = cfg.style_value("fonts.main", "assets/fonts/Montserrat-Bold.ttf")
        self.font_size = cfg.style_value("captions.font_size", 72)
        self.uppercase = cfg.style_value("captions.uppercase", False)
        self.highlight_on = cfg.style_value("captions.highlight_key_words", True)
        self.animation = cfg.style_value("captions.animation", "pop")  # pop | none (fade acts like none for now)
        self.y_fraction = _POSITIONS.get(cfg.style_value("captions.position", "lower_third"), 0.72)
        self.text_color = hex_to_rgb(cfg.style_value("colors.text", "#FFFFFF"))
        self.accent_color = hex_to_rgb(cfg.style_value("colors.accent", "#3DEBB5"))

        self.chunks = build_chunks(words, cfg.style_value("captions.words_per_line", 3))
        self._starts = [chunk.start for chunk in self.chunks]
        self._highlights = {_normalize(word) for word in highlight_words}

    def _chunk_at(self, t: float) -> CaptionChunk | None:
        index = bisect_right(self._starts, t) - 1
        if index < 0:
            return None
        chunk = self.chunks[index]
        return chunk if t <= chunk.end else None

    def _measure(self, texts: list[str], size: int):
        font = get_font(self.font_path, size)
        space = font.getlength(" ")
        widths = [font.getlength(text) for text in texts]
        return font, space, widths, sum(widths) + space * (len(texts) - 1)

    def draw(self, draw: ImageDraw.ImageDraw, t: float) -> None:
        """Draw the caption for time t (seconds) onto the frame."""
        if not self.enabled:
            return
        chunk = self._chunk_at(t)
        if chunk is None:
            return

        scale = 1.0
        if self.animation == "pop":  # grow from 80% to 100% as the caption appears
            scale = 0.8 + 0.2 * min(1.0, (t - chunk.start) / _POP_SECONDS)

        texts = [w.text.upper() if self.uppercase else w.text for w in chunk.words]
        size = max(8, int(self.font_size * scale))
        font, space, widths, total = self._measure(texts, size)

        max_width = self.width * 0.92  # shrink if the words don't fit on screen
        if total > max_width:
            size = max(8, int(size * max_width / total))
            font, space, widths, total = self._measure(texts, size)

        x = (self.width - total) / 2
        y = self.height * self.y_fraction
        stroke = max(2, size // 14)
        for word, text, width in zip(chunk.words, texts, widths):
            highlighted = self.highlight_on and _normalize(word.text) in self._highlights
            draw.text(
                (x, y), text, font=font, anchor="lm",
                fill=self.accent_color if highlighted else self.text_color,
                stroke_width=stroke, stroke_fill=(0, 0, 0),
            )
            x += width + space