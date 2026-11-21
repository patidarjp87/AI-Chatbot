"""paths.py - One place for every folder and file location.

If a folder ever moves, change it here and nothing else breaks.
"""
from pathlib import Path

# Project root = two levels above this file (src/utils/paths.py -> project root)
ROOT_DIR = Path(__file__).resolve().parents[2]

CONFIG_DIR = ROOT_DIR / "config"
ASSETS_DIR = ROOT_DIR / "assets"
INPUTS_DIR = ROOT_DIR / "inputs"
OUTPUT_DIR = ROOT_DIR / "output"
TMP_DIR = ROOT_DIR / "tmp"  # scratch space, never committed

SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
STYLE_FILE = CONFIG_DIR / "style.yaml"


def resolve(relative_path: str | Path) -> Path:
    """Turn a path from the config (like 'assets/fonts/x.ttf') into a full path."""
    path = Path(relative_path)
    return path if path.is_absolute() else ROOT_DIR / path


def ensure_dir(path: str | Path) -> Path:
    """Create a folder if it doesn't exist yet, and return its full path."""
    full_path = resolve(path)
    full_path.mkdir(parents=True, exist_ok=True)
    return full_path