"""test_youtube_upload.py - Checks the upload request we build. No internet or login needed."""
from datetime import datetime, timezone

import pytest

from src.config_loader import ConfigError
from src.models import Scene, VideoScript
from src.upload.youtube_provider import build_body

NOW = datetime(2026, 11, 23, 2, 30, tzinfo=timezone.utc)


def _script(title="Big news today", hashtags=None):
    return VideoScript(
        title=title,
        description="A summary.",
        hashtags=hashtags if hashtags is not None else ["#Shorts", "#WorldNews"],
        scenes=[Scene(text="Hello.")],
    )


def _body(mode, script=None, delay_hours=3):
    return build_body(
        script or _script(), mode=mode, delay_hours=delay_hours, category_id="25",
        language="en", made_for_kids=False, synthetic=False, now=NOW,
    )


def test_scheduled_mode_publishes_three_hours_later():
    status = _body("scheduled")["status"]
    assert status["privacyStatus"] == "private"
    assert status["publishAt"] == "2026-11-23T05:30:00Z"


def test_private_mode_has_no_publish_time():
    status = _body("private")["status"]
    assert status["privacyStatus"] == "private"
    assert "publishAt" not in status


def test_public_mode_is_public():
    assert _body("public")["status"]["privacyStatus"] == "public"


def test_unknown_mode_is_rejected():
    with pytest.raises(ConfigError):
        _body("someday")


def test_scheduled_mode_needs_a_positive_delay():
    with pytest.raises(ConfigError):
        _body("scheduled", delay_hours=0)


def test_title_is_cleaned_and_limited():
    snippet = _body("private", _script(title="<b>" + "x" * 200))["snippet"]
    assert len(snippet["title"]) <= 100
    assert "<" not in snippet["title"] and ">" not in snippet["title"]


def test_tags_come_from_hashtags_and_description_includes_them():
    snippet = _body("private")["snippet"]
    assert snippet["tags"] == ["Shorts", "WorldNews"]
    assert snippet["description"].endswith("#Shorts #WorldNews")