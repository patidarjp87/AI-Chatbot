"""drawing.py - Helpers for fonts, colors and text (used by captions and layouts).

get_font() returns a font object:
  - engine 'harfbuzz' (needed for Hindi): a HarfBuzzFont from src/utils/text_engine.py
  - engine 'pillow': a normal Pillow font (cannot join Hindi letters on Windows)
  - engine 'auto': harfbuzz when its packages are installed, otherwise pillow
Both kinds offer getlength(text). To draw text, always use draw_text() below.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.config_loader import ConfigError
from src.utils.logger import get_logger
from src.utils.paths import resolve

log = get_logger(__name__)

_ENGINES = ("auto", "harfbuzz", "pillow")

# Used only if the font in style.yaml is missing (the first two have Hindi)
_FALLBACK_FONTS = [
    "C:/Windows/Fonts/NirmalaB.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
_warned: set[str] = set()


def _warn_once(key: str, message: str, *args) -> None:
    """Log a warning only the first time (fonts are requested for every frame)."""
    if key not in _warned:
        _warned.add(key)
        log.warning(message, *args)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """'#3DEBB5' -> (61, 235, 181)"""
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def blend(color_a: tuple, color_b: tuple, amount: float) -> tuple[int, int, int]:
    """Mix two colors. amount=0 gives color_a, amount=1 gives color_b."""
    return tuple(int(a + (b - a) * amount) for a, b in zip(color_a, color_b))  # type: ignore[return-value]


def _find_font_file(configured_path: str) -> Path | None:
    """The font from style.yaml, or the first fallback font that exists."""
    configured = resolve(configured_path)
    if configured.exists():
        return configured
    for candidate in _FALLBACK_FONTS:
        path = resolve(candidate)
        if path.exists():
            _warn_once(configured_path, "Font '%s' not found. Using %s instead.", configured_path, path.name)
            return path
    return None


@lru_cache(maxsize=64)
def get_font(configured_path: str, size: int, engine: str = "auto"):
    """Load the font from style.yaml at a given size (cached, so it is fast)."""
    if engine not in _ENGINES:
        raise ConfigError(f"video.text_engine must be one of {', '.join(_ENGINES)} (got '{engine}')")

    path = _find_font_file(configured_path)
    if path is not None and engine in ("auto", "harfbuzz"):
        try:
            from src.utils.text_engine import HarfBuzzFont
            return HarfBuzzFont(path, size)
        except ImportError as exc:
            if engine == "harfbuzz":
                raise ConfigError(
                    "video.text_engine is 'harfbuzz' but its packages are missing. "
                    "Run: pip install -r requirements.txt"
                ) from exc
            _warn_once("no-harfbuzz", "uharfbuzz or freetype-py is not installed. Falling back to Pillow, "
                                       "so Hindi letters will NOT join correctly.")

    if path is None:
        _warn_once("no-font", "No usable font found. Using Pillow's default font.")
        try:
            return ImageFont.load_default(size=size)
        except TypeError:  # very old Pillow
            return ImageFont.load_default()
    return ImageFont.truetype(str(path), size)


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


def draw_text(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font,
    fill,
    anchor: str = "la",
    stroke_width: int = 0,
    stroke_fill=(0, 0, 0),
) -> None:
    """Draw text with either kind of font. `draw` must belong to `image`."""
    if hasattr(font, "draw_text"):  # HarfBuzzFont
        font.draw_text(image, xy, text, fill=fill, anchor=anchor,
                       stroke_width=stroke_width, stroke_fill=stroke_fill)
    else:  # normal Pillow font
        draw.text(xy, text, font=font, fill=fill, anchor=anchor,
                  stroke_width=stroke_width, stroke_fill=stroke_fill)


def font_ascent(font) -> float:
    """Pixels from the top of a text line down to its baseline."""
    if hasattr(font, "ascent"):  # HarfBuzzFont
        return font.ascent
    return font.getmetrics()[0]


def layer_from_masks(mask: Image.Image, outline: Image.Image | None, fill, stroke_fill=(0, 0, 0)) -> Image.Image:
    """Turn a text mask (and an optional outline mask) into an RGBA picture with clean edges.

    The transparent pixels get the SAME colour as the text, so no dark halo appears
    when the picture is blended over a background.
    """
    width, height = mask.size
    layer = Image.new("RGBA", (width, height), (*fill, 0))
    layer.paste((*fill, 255), (0, 0, width, height), mask)
    if outline is not None:
        under = Image.new("RGBA", (width, height), (*stroke_fill, 0))
        under.paste((*stroke_fill, 255), (0, 0, width, height), outline)
        layer = Image.alpha_composite(under, layer)
    return layer


def text_layer(text: str, font, fill, stroke_width: int = 0, stroke_fill=(0, 0, 0)):
    """Make a small transparent picture of one line of text.

    Returns (picture, (dx, dy)). To put the text's top-left corner (anchor 'la') at (x, y),
    paste the picture at (x - dx, y - dy). Works with both kinds of font.
    """
    if not text.strip():
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), (0, 0)
    if hasattr(font, "render_layer"):  # HarfBuzzFont
        return font.render_layer(text, fill, stroke_width, stroke_fill)

    pad = stroke_width + 2  # normal Pillow font
    left, top, right, bottom = font.getbbox(text, anchor="la", stroke_width=stroke_width)
    width, height = max(1, right - left) + 2 * pad, max(1, bottom - top) + 2 * pad
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).text((pad - left, pad - top), text, font=font, fill=255, anchor="la")
    outline = None
    if stroke_width > 0:
        outline = Image.new("L", (width, height), 0)
        ImageDraw.Draw(outline).text((pad - left, pad - top), text, font=font, fill=255,
                                     anchor="la", stroke_width=stroke_width)
    return layer_from_masks(mask, outline, fill, stroke_fill), (pad - left, pad - top)