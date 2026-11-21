"""config_loader.py - Reads settings.yaml, style.yaml and secret keys.

Every other file gets its settings through here, so nothing is hardcoded.
    cfg = load_config()
    cfg.setting("video.fps")            -> 30
    cfg.style_value("colors.accent")    -> "#3DEBB5"
    cfg.secret("GEMINI_API_KEY")        -> the key, or a clear error if missing
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from src.utils.paths import ROOT_DIR, SETTINGS_FILE, STYLE_FILE

# Sections that must exist in settings.yaml (catches typos early)
REQUIRED_SECTIONS = ("video", "news", "script", "voice", "footage", "upload", "output")


class ConfigError(Exception):
    """Raised with a readable message when config or a key is missing/invalid."""


def _read_yaml(path: Path) -> dict:
    """Read one YAML file and return it as a dictionary."""
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} must contain key: value settings")
    return data


def _lookup(data: dict, dotted_key: str, default: Any) -> Any:
    """Find 'video.formats.shorts' inside nested dictionaries."""
    node: Any = data
    for part in dotted_key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return default
    return node


@dataclass(frozen=True)
class Config:
    """Holds all settings. Create it with load_config()."""

    settings: dict
    style: dict

    def setting(self, key: str, default: Any = None) -> Any:
        """Read a value from settings.yaml using dots, e.g. 'script.provider'."""
        return _lookup(self.settings, key, default)

    def style_value(self, key: str, default: Any = None) -> Any:
        """Read a value from style.yaml using dots, e.g. 'captions.font_size'."""
        return _lookup(self.style, key, default)

    def secret(self, env_name: str) -> str:
        """Get an API key from the environment (.env locally, GitHub Secrets in the cloud)."""
        value = os.getenv(env_name, "").strip()
        if not value:
            raise ConfigError(
                f"Missing key '{env_name}'. Add it to your .env file "
                f"(or GitHub Secrets when running in the cloud)."
            )
        return value

    @property
    def video_size(self) -> tuple[int, int, int]:
        """Returns (width, height, max_seconds) for the chosen video.format."""
        video_format = self.setting("video.format")
        spec = self.setting(f"video.formats.{video_format}")
        if not spec:
            raise ConfigError(f"video.format '{video_format}' has no entry in video.formats")
        return spec["width"], spec["height"], spec["max_seconds"]


def load_config() -> Config:
    """Load .env (if present), both YAML files, and check the basics."""
    load_dotenv(ROOT_DIR / ".env", override=False)  # does nothing if .env is absent
    settings = _read_yaml(SETTINGS_FILE)
    style = _read_yaml(STYLE_FILE)

    missing = [name for name in REQUIRED_SECTIONS if name not in settings]
    if missing:
        raise ConfigError(f"settings.yaml is missing sections: {', '.join(missing)}")

    return Config(settings=settings, style=style)