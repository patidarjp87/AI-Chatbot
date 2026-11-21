"""drawing.py - Small helpers for fonts, colors and text wrapping (used by captions and layouts)."""
from __future__ import annotations

from functools import lru_cache

from PIL import ImageFont

from src.utils.logger import get_logger
from src.utils.paths import resolve

log = get_logger(__name__)

# Used only if the font in style.yaml is missing
_FALLBACK_FONTS = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
_warned: set[str] = set()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """'#3DEBB5' -> (61, 235, 181)"""
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def blend(color_a: tuple, color_b: tuple, amount: float) -> tuple[int, int, int]:
    """Mix two colors. amount=0 gives color_a, amount=1 gives color_b."""
    return tuple(int(a + (b - a) * amount) for a, b in zip(color_a, color_b))  # type: ignore[return-value]


@lru_cache(maxsize=64)
def get_font(configured_path: str, size: int):
    """Load the font from style.yaml at a given size (cached, so it's fast)."""
    candidates = [resolve(configured_path)] + [resolve(p) for p in _FALLBACK_FONTS]
    for index, path in enumerate(candidates):
        if path.exists():
            if index > 0 and configured_path not in _warned:
                _warned.add(configured_path)
                log.warning("Font '%s' not found. Using %s instead.", configured_path, path.name)
            return ImageFont.truetype(str(path), size)
    log.warning("No usable font found. Using Pillow's default font.")
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def wrap_text(text: str, font, max_width: float) -> list[str]:
    """Split text into lines that fit inside max_width pixels."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if not current or font.getlength(trial) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines