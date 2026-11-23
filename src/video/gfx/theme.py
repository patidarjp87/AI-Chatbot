"""theme.py - Reads the motion-graphics design system (style.yaml -> theme:) and validates it.

Every colour, size, timing and font used by the graphics comes from here, so changing the
look means editing style.yaml, not code. Sizes are written for a 1080-pixel reference and
scaled by `unit` for other frame sizes.
"""
from __future__ import annotations

from src.config_loader import Config, ConfigError
from src.utils.drawing import get_font, hex_to_rgb
from src.utils.logger import get_logger
from src.utils.paths import resolve
from src.video.gfx.easing import EASINGS

log = get_logger(__name__)

TONES = ("cyan", "teal", "warning", "danger", "success")

DEFAULT_COLORS = {
    "background": "#101827", "background_secondary": "#172536", "card": "#1D3345",
    "card_border": "#2B4A63", "text": "#F5F7FA", "text_secondary": "#A9B7C7",
    "cyan": "#43D9E5", "teal": "#42D6B2", "warning": "#FFBE55",
    "danger": "#FF657A", "success": "#45D6A0",
}
DEFAULT_SIZES = {"heading": 96, "subheading": 72, "title": 52, "body": 46, "value": 150, "small": 38}
DEFAULT_SAFE = {
    "shorts": {"left": 0.06, "top": 0.08, "right": 0.12, "bottom": 0.20},
    "long": {"left": 0.05, "top": 0.06, "right": 0.05, "bottom": 0.08},
}


def _color(cfg: Config, name: str, default: str) -> tuple[int, int, int]:
    value = cfg.style_value(f"theme.colors.{name}", default)
    try:
        rgb = hex_to_rgb(str(value))
        if len(rgb) != 3:
            raise ValueError
    except (ValueError, TypeError):
        raise ConfigError(f"style.yaml theme.colors.{name} must be a colour like '#43D9E5' (got {value!r})") from None
    return rgb


def _number(cfg: Config, key: str, default: float, low: float, high: float) -> float:
    value = cfg.style_value(key, default)
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ConfigError(f"style.yaml {key} must be a number (got {value!r})") from None
    if not low <= number <= high:
        raise ConfigError(f"style.yaml {key} must be between {low} and {high} (got {number})")
    return number


class Theme:
    def __init__(self, cfg: Config):
        self.width, self.height, _ = cfg.video_size
        self.unit = min(self.width, self.height) / 1080  # scale factor for sizes

        self.colors = {name: _color(cfg, name, default) for name, default in DEFAULT_COLORS.items()}
        self.sizes = {
            name: int(_number(cfg, f"theme.type.{name}", default, 8, 600))
            for name, default in DEFAULT_SIZES.items()
        }

        self.radius = self.px(_number(cfg, "theme.card.radius", 36, 0, 200))
        self.padding = self.px(_number(cfg, "theme.card.padding", 44, 8, 200))
        self.border_width = max(1, self.px(_number(cfg, "theme.card.border_width", 3, 0, 20)))
        self.shadow_blur = self.px(_number(cfg, "theme.card.shadow_blur", 28, 0, 120))
        self.shadow_opacity = _number(cfg, "theme.card.shadow_opacity", 0.45, 0, 1)
        self.shadow_offset = self.px(_number(cfg, "theme.card.shadow_offset", 14, 0, 80))

        self.grid_spacing = max(24, self.px(_number(cfg, "theme.grid.spacing", 96, 24, 400)))
        self.grid_line_alpha = _number(cfg, "theme.grid.line_alpha", 0.07, 0, 1)
        self.grid_drift = _number(cfg, "theme.grid.drift", 18, 0, 300) * self.unit
        self.grid_vignette = _number(cfg, "theme.grid.vignette", 0.30, 0, 0.9)

        self.fade = _number(cfg, "theme.motion.fade_seconds", 0.45, 0.05, 3)
        self.reveal = _number(cfg, "theme.motion.reveal_seconds", 0.6, 0.05, 4)
        self.stagger = _number(cfg, "theme.motion.stagger_seconds", 0.18, 0, 2)
        self.slide = self.px(_number(cfg, "theme.motion.slide_pixels", 140, 0, 600))
        self.ease_name = str(cfg.style_value("theme.motion.ease", "out_cubic"))
        if self.ease_name not in EASINGS:
            raise ConfigError(f"style.yaml theme.motion.ease must be one of: {', '.join(EASINGS)}")
        self.supersample = int(_number(cfg, "theme.supersample", 2, 1, 4))

        self.heading_font = str(cfg.style_value("theme.fonts.heading", "assets/fonts/Hind-Bold.ttf"))
        body = str(cfg.style_value("theme.fonts.body", "assets/fonts/Hind-Medium.ttf"))
        if not resolve(body).exists():
            log.warning("Body font %s not found. Using the heading font instead.", body)
            body = self.heading_font
        self.body_font = body
        self.text_engine = cfg.setting("video.text_engine", "auto")

        # Safe area: margins in pixels that keep content clear of YouTube's buttons and title
        key = "long" if cfg.setting("video.format") == "long" else "shorts"
        fractions = {side: _number(cfg, f"theme.safe_area.{key}.{side}", DEFAULT_SAFE[key][side], 0, 0.4)
                     for side in ("left", "top", "right", "bottom")}
        self.safe = (
            round(self.width * fractions["left"]), round(self.height * fractions["top"]),
            round(self.width * fractions["right"]), round(self.height * fractions["bottom"]),
        )

    @classmethod
    def from_config(cls, cfg: Config) -> "Theme":
        return cls(cfg)

    def px(self, value: float) -> int:
        """Scale a size written for a 1080-pixel frame."""
        return round(value * self.unit)

    def color(self, name: str) -> tuple[int, int, int]:
        if name not in self.colors:
            raise ValueError(f"Unknown colour '{name}'")
        return self.colors[name]

    def tone_color(self, tone: str) -> tuple[int, int, int]:
        """The colour for a tone: cyan, teal, warning, danger or success."""
        if tone not in TONES:
            raise ValueError(f"Unknown tone '{tone}'. Available: {', '.join(TONES)}")
        return self.colors[tone]

    def size(self, key: str, scale: float = 1.0) -> int:
        if key not in self.sizes:
            raise ValueError(f"Unknown text size '{key}'. Available: {', '.join(self.sizes)}")
        return max(8, round(self.sizes[key] * self.unit * scale))

    def font(self, kind: str, size_key: str, scale: float = 1.0):
        """A font: kind is 'heading' or 'body'; size_key is one of the sizes in style.yaml."""
        path = self.heading_font if kind == "heading" else self.body_font
        return get_font(path, self.size(size_key, scale), self.text_engine)