"""layers.py - Cached pictures (sprites) and how to place them on a frame.

Idea: shapes and text are drawn ONCE (large, then shrunk, for smooth edges) into RGBA
sprites. Each frame only moves, fades or scales those sprites, which is fast.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

from src.video.gfx.theme import Theme


def rounded_card(theme: Theme, width: int, height: int, fill, border, accent=None) -> tuple[Image.Image, int]:
    """A rounded card with a soft shadow. Returns (sprite, margin).

    The card itself starts at (margin, margin) inside the sprite; the margin holds the shadow.
    `accent` adds a coloured strip on the left edge.
    """
    ss = theme.supersample
    radius = theme.radius
    margin = int(theme.shadow_blur * 1.6 + theme.shadow_offset) + 2
    full = ((width + 2 * margin) * ss, (height + 2 * margin) * ss)
    left, top = margin * ss, margin * ss
    right, bottom = (margin + width) * ss - 1, (margin + height) * ss - 1

    shadow_mask = Image.new("L", full, 0)
    shift = theme.shadow_offset * ss
    ImageDraw.Draw(shadow_mask).rounded_rectangle(
        [left, top + shift, right, bottom + shift], radius=radius * ss, fill=int(255 * theme.shadow_opacity)
    )
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(max(0.1, theme.shadow_blur * ss / 2)))
    layer = Image.new("RGBA", full, (0, 0, 0, 0))
    layer.paste((0, 0, 0, 255), (0, 0, full[0], full[1]), shadow_mask)

    card = Image.new("RGBA", full, (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    if accent is not None:
        draw.rounded_rectangle([left, top, right, bottom], radius=radius * ss, fill=(*accent, 255))
        strip = theme.px(16) * ss
        draw.rounded_rectangle([left + strip, top, right, bottom], radius=radius * ss, fill=(*fill, 255))
    else:
        draw.rounded_rectangle([left, top, right, bottom], radius=radius * ss, fill=(*fill, 255))
    draw.rounded_rectangle([left, top, right, bottom], radius=radius * ss,
                           outline=(*border, 255), width=theme.border_width * ss)

    layer = Image.alpha_composite(layer, card)
    size = (width + 2 * margin, height + 2 * margin)
    return layer.resize(size, Image.Resampling.LANCZOS), margin


def rounded_rect_sprite(theme: Theme, width: int, height: int, radius: int, color) -> Image.Image:
    """A solid rounded bar (used for underlines and progress bars) with smooth edges."""
    ss = theme.supersample
    width, height = max(1, int(width)), max(1, int(height))
    big = Image.new("RGBA", (width * ss, height * ss), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle(
        [0, 0, width * ss - 1, height * ss - 1], radius=max(0, radius) * ss, fill=(*color, 255)
    )
    return big.resize((width, height), Image.Resampling.LANCZOS)


def composite(frame: Image.Image, sprite: Image.Image, x: float, y: float,
              alpha: float = 1.0, scale: float = 1.0) -> None:
    """Paste an RGBA sprite onto an RGB frame.

    (x, y) is the sprite's top-left corner before scaling; scaling happens around its centre.
    alpha: 0 = invisible, 1 = fully visible.
    """
    if alpha <= 0.003:
        return
    image = sprite
    if abs(scale - 1.0) > 0.002:
        width, height = sprite.size
        new_w, new_h = max(1, round(width * scale)), max(1, round(height * scale))
        image = sprite.resize((new_w, new_h), Image.Resampling.BILINEAR)
        x += (width - new_w) / 2
        y += (height - new_h) / 2
    if alpha < 0.997:
        image = image.copy()
        image.putalpha(image.getchannel("A").point(lambda value: int(value * alpha)))
    frame.paste(image, (round(x), round(y)), image)


class GridBackground:
    """The dark navy background with a subtle technical grid that drifts slowly."""

    def __init__(self, theme: Theme):
        width, height, spacing = theme.width, theme.height, theme.grid_spacing
        size = (width, height + spacing)
        top = Image.new("RGB", size, theme.color("background"))
        bottom = Image.new("RGB", size, theme.color("background_secondary"))
        gradient = Image.linear_gradient("L").resize(size)
        base = Image.composite(bottom, top, gradient).convert("RGBA")

        lines = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(lines)
        line_color = (*theme.color("cyan"), int(255 * theme.grid_line_alpha))
        for y in range(0, size[1] + 1, spacing):
            draw.line([(0, y), (width, y)], fill=line_color, width=2)
        for x in range(0, width + 1, spacing):
            draw.line([(x, 0), (x, size[1])], fill=line_color, width=2)
        base = Image.alpha_composite(base, lines).convert("RGB")

        vignette = Image.radial_gradient("L").resize(size).point(lambda v: int(v * theme.grid_vignette))
        self._image = Image.composite(Image.new("RGB", size, (0, 0, 0)), base, vignette)
        self._width, self._height = width, height
        self._spacing = spacing
        self._drift = theme.grid_drift

    def frame(self, t: float) -> Image.Image:
        """A fresh copy of the background for time t (the grid has moved a little)."""
        offset = int((t * self._drift) % self._spacing)
        top = self._spacing - offset
        return self._image.crop((0, top, self._width, top + self._height))