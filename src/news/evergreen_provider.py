"""evergreen_provider.py - Gives the pipeline ONE topic from a hand-written list.

PHASE 1 TEST SOURCE ONLY. The topics are not checked against official sources, so
videos made from them must never be published. The pipeline blocks non-private uploads
while this provider is active.

Settings (settings.yaml -> news.evergreen): topics_file, pick (rotate | random), topic_id.
"""
from __future__ import annotations

import random
from datetime import date

import yaml

from src.config_loader import Config, ConfigError
from src.models import NewsItem
from src.news.base import NewsProvider
from src.utils.dates import today_string
from src.utils.logger import get_logger
from src.utils.paths import resolve

log = get_logger(__name__)

SOURCE_LABEL = "Internal test topic list (not source-verified)"
PICK_MODES = ("rotate", "random")


def load_topics(path) -> list[dict]:
    """Read the topic list and check that every topic has an id, a title and a brief."""
    file = resolve(path)
    if not file.is_file():
        raise ConfigError(f"Topic file not found: {file}")
    data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    topics = data.get("topics") if isinstance(data, dict) else None
    if not isinstance(topics, list) or not topics:
        raise ConfigError(f"{file.name} must contain a non-empty 'topics:' list")
    for number, topic in enumerate(topics, start=1):
        if not isinstance(topic, dict):
            raise ConfigError(f"Topic {number} in {file.name} is not a set of fields")
        for field in ("id", "title", "brief"):
            if not str(topic.get(field, "")).strip():
                raise ConfigError(f"Topic {number} in {file.name} is missing '{field}'")
    return topics


def choose_topic(topics: list[dict], pick: str, forced_id: str, today: date) -> dict:
    """Choose today's topic: a forced one, a date-based rotation, or a random one."""
    if forced_id:
        for topic in topics:
            if str(topic["id"]) == forced_id:
                return topic
        ids = ", ".join(str(topic["id"]) for topic in topics)
        raise ConfigError(f"news.evergreen.topic_id '{forced_id}' not found. Available: {ids}")
    if pick == "random":
        return random.choice(topics)
    return topics[today.toordinal() % len(topics)]  # rotate: a different topic each day


class EvergreenNewsProvider(NewsProvider):
    def fetch(self) -> list[NewsItem]:
        pick = str(self.cfg.setting("news.evergreen.pick", "rotate")).lower()
        if pick not in PICK_MODES:
            raise ConfigError(f"news.evergreen.pick must be one of {', '.join(PICK_MODES)}")
        topics = load_topics(self.cfg.setting("news.evergreen.topics_file", "config/topics_evergreen.yaml"))
        today = date.fromisoformat(today_string(self.cfg.setting("project.timezone")))
        topic = choose_topic(topics, pick, str(self.cfg.setting("news.evergreen.topic_id", "") or ""), today)

        log.info("Topic for today: %s (%s). TEST topic, not source-verified.", topic["title"], topic["id"])
        return [NewsItem(
            title=str(topic["title"]).strip(),
            summary=" ".join(str(topic["brief"]).split()),  # collapse line breaks into one paragraph
            link="",
            source=SOURCE_LABEL,
            published=today.isoformat(),
        )]