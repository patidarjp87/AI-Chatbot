"""base.py (components) - Shared parts of every animated graphic.

A component is placed in a rectangle (box) of the frame. It is built once (static pictures
are cached), and draw(frame, t, duration) then paints the state at time t, where t is seconds
since the component appeared. validate(spec) checks the scene data and raises ValueError with
a readable message if it is unusable.
"""
from __future__ import annotations

import unicodedata

from PIL import Image

from src.video.gfx.theme import Theme


def clean_text(spec: dict, key: str, max_chars: int, required: bool = False) -> str:
    """Read a text field from a scene spec: tidy spaces and check the length."""
    value = spec.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, (str, int, float)):
        raise ValueError(f"'{key}' must be text")
    text = " ".join(str(value).split())
    if required and not text:
        raise ValueError(f"'{key}' is required")
    if len(text) > max_chars:
        raise ValueError(f"'{key}' is too long ({len(text)} characters, the maximum is {max_chars})")
    return text


def choice(spec: dict, key: str, allowed: tuple, default: str) -> str:
    """Read a field that must be one of a few allowed words."""
    value = str(spec.get(key) or default).lower()
    if value not in allowed:
        raise ValueError(f"'{key}' must be one of: {', '.join(allowed)} (got '{value}')")
    return value


def as_word_list(value) -> list[str]:
    """Accept a string or a list of strings and return a list of words."""
    if not value:
        return []
    if isinstance(value, str):
        return value.split()
    if isinstance(value, list):
        return [word for item in value for word in str(item).split()]
    raise ValueError("'highlight' must be text or a list of words")


def normalize_word(word: str) -> str:
    """Lowercase and drop punctuation, but keep letters, digits and Hindi vowel signs."""
    return "".join(
        ch for ch in word.lower()
        if ch.isalnum() or ch == "'" or unicodedata.category(ch).startswith("M")
    )


def wrap_words(words: list[str], font, max_width: float) -> list[list[str]]:
    """Split words into lines that fit max_width (a single very long word gets its own line)."""
    space = font.getlength(" ")
    lines: list[list[str]] = []
    current: list[str] = []
    width = 0.0
    for word in words:
        word_width = font.getlength(word)
        extra = word_width if not current else space + word_width
        if current and width + extra > max_width:
            lines.append(current)
            current, width = [word], word_width
        else:
            current.append(word)
            width += extra
    if current:
        lines.append(current)
    return lines


class Component:
    visual_type = ""

    def __init__(self, theme: Theme, spec: dict, box: tuple[int, int, int, int]):
        self.theme = theme
        self.spec = spec
        self.x, self.y, self.w, self.h = box

    @staticmethod
    def validate(spec: dict) -> dict:
        raise NotImplementedError

    def draw(self, frame: Image.Image, t: float, duration: float) -> None:
        raise NotImplementedError