"""test_config.py - Checks that the config files load and make sense."""
from src.config_loader import load_config


def test_config_loads():
    cfg = load_config()
    assert cfg.setting("video.format") in ("shorts", "long")


def test_shorts_are_vertical():
    cfg = load_config()
    width, height, _ = cfg.video_size
    if cfg.setting("video.format") == "shorts":
        assert height > width  # 9:16 vertical


def test_missing_setting_returns_default():
    cfg = load_config()
    assert cfg.setting("does.not.exist", "fallback") == "fallback"