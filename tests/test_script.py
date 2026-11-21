"""test_script.py - Checks the sample script fits the video length and providers load."""
import pytest

from src.config_loader import ConfigError, load_config
from src.models import NewsItem
from src.script.sample_provider import SampleScriptProvider
from src.utils.registry import load_provider


def test_sample_script_fits_word_budget():
    cfg = load_config()
    items = [
        NewsItem(title=f"Headline number {i} about something big happening", summary="Some detail here. More.")
        for i in range(12)
    ]
    script = SampleScriptProvider(cfg).generate(items)
    _, _, max_seconds = cfg.video_size
    max_words = cfg.setting("script.speaking_rate_wpm") * max_seconds / 60
    assert script.word_count <= max_words
    assert len(script.scenes) >= 3  # intro + at least one story + outro


def test_unknown_provider_gives_clear_error():
    with pytest.raises(ConfigError):
        load_provider("news", "nope", {"rss": "src.news.rss_provider:RssNewsProvider"})