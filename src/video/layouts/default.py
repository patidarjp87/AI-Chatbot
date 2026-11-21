"""default.py - The default look: animated grid background, progress bar,
headline cards that slide in, and captions.

A layout is a class named `Layout` with a render(t) method that returns one frame.
To add a new look, copy this file, change it, and add its name to
style.yaml -> allowed_layouts. Then set video.layout in settings.yaml.
"""
from __future__ import annotations

from bisect import bisect_right

from PIL import Image, ImageDraw

from src.config_loader import Config
from src.models import FootageClip, VideoScript, VoiceResult
from src.utils.drawing import blend, get_font, hex_to_rgb, wrap_text
from src.utils.logger import get_logger
from src.utils.paths import resolve
from src.video.captions import CaptionRenderer

log = get_logger(__name__)

_GRID_SPACING = 120      # pixels between grid lines
_GRID_SPEED = 60         # pixels per second the grid scrolls
_SLIDE_SECONDS = 0.35    # how long the headline card takes to slide in
_END_PADDING = 0.4       # extra seconds of video after the voice ends


def scene_windows(script: VideoScript, voice: VoiceResult) -> list[tuple[float, float]]:
    """Work out when each scene starts and ends, using the word timings.

    Scenes are matched to words by position (scene 1 = first N words, and so on).
    """
    counts = [len(scene.text.split()) for scene in script.scenes]
    total = sum(counts) or 1
    word_count = len(voice.words)

    starts: list[float] = []
    cumulative = 0
    for count in counts:
        if word_count:
            index = min(round(cumulative * word_count / total), word_count - 1)
            starts.append(voice.words[index].start)
        else:
            starts.append(0.0)
        cumulative += count
    starts[0] = 0.0
    ends = starts[1:] + [voice.duration_seconds + _END_PADDING]
    return list(zip(starts, ends))


class Layout:
    def __init__(self, cfg: Config, script: VideoScript, voice: VoiceResult, footage: list[FootageClip]):
        self.cfg = cfg
        self.script = script
        self.width, self.height, _ = cfg.video_size
        self.total_seconds = voice.duration_seconds + _END_PADDING
        # NOTE: `footage` is not used yet. When stock clips exist, draw the clip's
        # frame for each scene in _background() instead of the grid.

        # Colors and fonts (all from style.yaml)
        self.bg = hex_to_rgb(cfg.style_value("colors.background", "#0B0F14"))
        self.accent = hex_to_rgb(cfg.style_value("colors.accent", "#3DEBB5"))
        self.text_color = hex_to_rgb(cfg.style_value("colors.text", "#FFFFFF"))
        self.bar_color = hex_to_rgb(cfg.style_value("colors.headline_bar", "#111820"))
        self.font_path = cfg.style_value("fonts.main", "assets/fonts/Montserrat-Bold.ttf")

        # Headline card settings
        self.card_enabled = cfg.style_value("headline_card.enabled", True)
        self.card_seconds = cfg.style_value("headline_card.show_seconds", 2.5)
        self.card_font_size = cfg.style_value("headline_card.font_size", 64)

        # Timing, captions, background, logo
        windows = scene_windows(script, voice)
        self._scene_starts = [start for start, _ in windows]
        highlights = [word for scene in script.scenes for word in scene.highlight_words]
        self.captions = CaptionRenderer(cfg, voice.words, highlights, (self.width, self.height))
        self._grid = self._make_grid()
        self._logo = self._load_logo()

    # ---------- background ----------
    def _make_grid(self) -> Image.Image:
        """Draw a grid once. We crop it at a moving offset to make it scroll."""
        image = Image.new("RGB", (self.width, self.height + _GRID_SPACING), self.bg)
        draw = ImageDraw.Draw(image)
        line_color = blend(self.bg, self.accent, 0.12)
        for y in range(0, self.height + _GRID_SPACING + 1, _GRID_SPACING):
            draw.line([(0, y), (self.width, y)], fill=line_color, width=2)
        for x in range(0, self.width + 1, _GRID_SPACING):
            draw.line([(x, 0), (x, self.height + _GRID_SPACING)], fill=line_color, width=2)
        return image

    def _background(self, t: float) -> Image.Image:
        offset = int((t * _GRID_SPEED) % _GRID_SPACING)
        top = _GRID_SPACING - offset
        return self._grid.crop((0, top, self.width, top + self.height))

    # ---------- logo ----------
    def _load_logo(self) -> Image.Image | None:
        if not self.cfg.style_value("logo.enabled", False):
            return None
        path = resolve(self.cfg.style_value("logo.file", "assets/logo/logo.png"))
        if not path.exists():
            log.warning("Logo enabled but file not found: %s", path)
            return None
        logo = Image.open(path).convert("RGBA")
        target_width = int(self.width * 0.18)
        logo = logo.resize((target_width, int(logo.height * target_width / logo.width)))
        opacity = float(self.cfg.style_value("logo.opacity", 0.8))
        logo.putalpha(logo.getchannel("A").point(lambda a: int(a * opacity)))
        return logo

    def _draw_logo(self, image: Image.Image) -> None:
        if self._logo is None:
            return
        margin = 40
        if self.cfg.style_value("logo.position", "top_right") == "top_left":
            x = margin
        else:
            x = self.width - self._logo.width - margin
        image.paste(self._logo, (x, int(self.height * 0.05)), self._logo)

    # ---------- foreground pieces ----------
    def _draw_progress_bar(self, draw: ImageDraw.ImageDraw, t: float) -> None:
        filled = int(self.width * min(1.0, t / self.total_seconds))
        top = int(self.height * 0.035)
        draw.rectangle([0, top, filled, top + 12], fill=self.accent)

    def _draw_headline_card(self, draw: ImageDraw.ImageDraw, t: float, scene_index: int) -> None:
        text = self.script.scenes[scene_index].on_screen_text
        local = t - self._scene_starts[scene_index]
        if not self.card_enabled or not text or local > self.card_seconds:
            return

        progress = min(1.0, local / _SLIDE_SECONDS)
        ease = 1 - (1 - progress) ** 3  # starts fast, slows at the end
        card_width = int(self.width * 0.84)
        font = get_font(self.font_path, self.card_font_size)
        lines = wrap_text(text.upper(), font, card_width - 90)[:3]
        line_height = int(self.card_font_size * 1.25)
        card_height = len(lines) * line_height + 60

        x0 = int(self.width * 0.08 - (1 - ease) * self.width)  # slides in from the left
        y0 = int(self.height * 0.20)
        draw.rounded_rectangle([x0, y0, x0 + card_width, y0 + card_height], radius=24, fill=self.bar_color)
        draw.rectangle([x0, y0, x0 + 14, y0 + card_height], fill=self.accent)
        for i, line in enumerate(lines):
            draw.text((x0 + 44, y0 + 30 + i * line_height), line, font=font, fill=self.text_color, anchor="lt")

    # ---------- one frame ----------
    def render(self, t: float) -> Image.Image:
        """Return the full frame for time t (in seconds)."""
        image = self._background(t)
        draw = ImageDraw.Draw(image)
        scene_index = max(0, bisect_right(self._scene_starts, t) - 1)

        self._draw_progress_bar(draw, t)
        self._draw_headline_card(draw, t, scene_index)
        self.captions.draw(draw, t)
        self._draw_logo(image)
        return image