"""test_gemini_parse.py - Checks how we read Gemini's answer. No internet or key needed."""
import json

import pytest

from src.config_loader import load_config
from src.models import Scene, VideoScript
from src.script.gemini_provider import fit_length, parse_script, word_limits

GOOD = {
    "title": "Test headline",
    "description": "A summary.\nSources: BBC",
    "hashtags": ["News", "#Shorts"],
    "layout": "default",
    "scenes": [
        {"text": "Big news today.", "keyword": "city skyline", "on_screen_text": "Big News",
         "highlight_words": ["news"], "presenter_moment": False},
        {"text": "Follow for more.", "keyword": "", "on_screen_text": "", "highlight_words": []},
    ],
}


def test_parses_valid_json():
    script = parse_script(json.dumps(GOOD), load_config())
    assert script.title == "Test headline"
    assert len(script.scenes) == 2
    assert "#News" in script.hashtags  # missing '#' is added


def test_parses_json_inside_code_fence():
    raw = "```json\n" + json.dumps(GOOD) + "\n```"
    assert len(parse_script(raw, load_config()).scenes) == 2


def test_missing_scenes_is_rejected():
    with pytest.raises(ValueError):
        parse_script(json.dumps({"title": "x"}), load_config())


def test_too_long_script_is_trimmed_but_keeps_first_and_last():
    scenes = [Scene(text=" ".join(["word"] * 40)) for _ in range(5)]
    scenes[0].text = "FIRST " + scenes[0].text
    scenes[-1].text = "LAST " + scenes[-1].text
    script = VideoScript(title="t", description="", hashtags=[], scenes=scenes)
    _, max_words = word_limits(load_config())
    fit_length(script, max_words)
    assert script.word_count <= max_words
    assert script.scenes[0].text.startswith("FIRST")
    assert script.scenes[-1].text.startswith("LAST")