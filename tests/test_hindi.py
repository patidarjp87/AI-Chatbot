"""test_hindi.py - Checks the Hindi-related fixes and the topic list. Works offline."""
import json
from datetime import date

import pytest

from src.config_loader import ConfigError, load_config
from src.models import WordTiming
from src.news.evergreen_provider import choose_topic, load_topics
from src.pipeline import _slugify
from src.script.gemini_provider import parse_script
from src.upload.youtube_provider import _tags
from src.utils.paths import resolve
from src.utils.text_engine import HarfBuzzFont, split_runs
from src.video.captions import _normalize, build_chunks

TOPICS = [
    {"id": "a", "title": "A", "brief": "x"},
    {"id": "b", "title": "B", "brief": "y"},
    {"id": "c", "title": "C", "brief": "z"},
]


def test_normalize_keeps_hindi_letters_and_vowel_signs():
    assert _normalize("स्कैम,") == "स्कैम"
    assert _normalize("OTP!") == "otp"


def test_danda_ends_a_caption_group():
    words = [WordTiming(w, i * 0.3, i * 0.3 + 0.25) for i, w in enumerate(["यह", "ठगी।", "सावधान", "रहें"])]
    assert [len(chunk.words) for chunk in build_chunks(words, 3)] == [2, 2]


def test_youtube_tags_keep_hindi():
    assert _tags(["#साइबरसुरक्षा", "#Shorts"]) == ["साइबरसुरक्षा", "Shorts"]


def test_hindi_title_has_no_english_slug():
    assert _slugify("साइबर सुरक्षा") == ""
    assert _slugify("OTP Fraud Basics") == "otp-fraud-basics"


def test_split_runs_separates_scripts():
    assert split_runs("UPI स्कैम") == [("Latn", "UPI "), ("Deva", "स्कैम")]


def test_text_engine_measures_hindi_text():
    font_file = resolve("assets/fonts/Hind-Bold.ttf")
    if not font_file.exists():
        pytest.skip("Hind-Bold.ttf is not in assets/fonts")
    font = HarfBuzzFont(font_file, 72)
    assert font.getlength("स्कैम") > 0
    assert font.getlength("स्कैम स्कैम") > font.getlength("स्कैम")


def test_rotation_changes_with_the_date():
    today = choose_topic(TOPICS, "rotate", "", date(2026, 11, 23))["id"]
    tomorrow = choose_topic(TOPICS, "rotate", "", date(2026, 11, 24))["id"]
    assert today != tomorrow


def test_forced_topic_wins_and_unknown_topic_is_rejected():
    assert choose_topic(TOPICS, "rotate", "b", date(2026, 11, 23))["id"] == "b"
    with pytest.raises(ConfigError):
        choose_topic(TOPICS, "rotate", "zzz", date(2026, 11, 23))


def test_real_topic_file_is_valid():
    topics = load_topics("config/topics_evergreen.yaml")
    assert len(topics) >= 5
    assert len({str(topic["id"]) for topic in topics}) == len(topics)  # ids are unique


def test_parse_script_reads_hindi_and_slug():
    raw = json.dumps({
        "title": "ओटीपी किसी को न बताएं",
        "slug": "OTP Fraud Basics!",
        "description": "विवरण\n\nSources: test",
        "hashtags": ["#Shorts", "#डिजिटलसमझ"],
        "layout": "default",
        "scenes": [
            {"text": "क्या आपने कभी ओटीपी साझा किया है?", "keyword": "smartphone typing",
             "on_screen_text": "OTP का सच", "highlight_words": ["ओटीपी"]},
            {"text": "फॉलो करें।", "keyword": "", "on_screen_text": "", "highlight_words": []},
        ],
    }, ensure_ascii=False)
    script = parse_script(raw, load_config())
    assert script.slug == "otp-fraud-basics"
    assert script.scenes[0].text.startswith("क्या")
    assert "#डिजिटलसमझ" in script.hashtags