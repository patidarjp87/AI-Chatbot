"""rss_provider.py - Reads headlines from free RSS feeds (list is in settings.yaml)."""
import html
import re

import feedparser
import requests

from src.config_loader import ConfigError
from src.models import NewsItem
from src.news.base import NewsProvider
from src.utils.logger import get_logger
from src.utils.retry import retry

log = get_logger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    """Remove HTML tags and extra spaces from feed text."""
    text = html.unescape(_TAG_RE.sub(" ", text or ""))
    return _SPACE_RE.sub(" ", text).strip()


class RssNewsProvider(NewsProvider):
    def fetch(self) -> list[NewsItem]:
        feeds = self.cfg.setting("news.rss.feeds", [])
        max_items = self.cfg.setting("news.max_items", 10)
        if not feeds:
            raise ConfigError("news.rss.feeds is empty in settings.yaml")

        per_feed: list[list[NewsItem]] = []
        for url in feeds:
            try:
                per_feed.append(self._read_feed(url)[:max_items])
            except Exception as exc:  # one broken feed should not stop the run
                log.warning("Skipping feed %s: %s", url, exc)

        # Take items round-robin so one source doesn't dominate
        items: list[NewsItem] = []
        seen_titles: set[str] = set()
        for position in range(max_items):
            for feed_items in per_feed:
                if position < len(feed_items):
                    item = feed_items[position]
                    key = item.title.lower()
                    if item.title and key not in seen_titles:
                        seen_titles.add(key)
                        items.append(item)

        items = items[:max_items]
        if not items:
            raise RuntimeError("No news items could be fetched. Check your internet and feed URLs.")
        log.info("Fetched %d news items from %d feeds", len(items), len(per_feed))
        return items

    @retry(attempts=3, delay=2, exceptions=(requests.RequestException,))
    def _read_feed(self, url: str) -> list[NewsItem]:
        """Download one feed and convert its entries to NewsItem objects."""
        response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (news-shorts)"})
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        source = _clean(parsed.feed.get("title", url))
        return [
            NewsItem(
                title=_clean(entry.get("title", "")),
                summary=_clean(entry.get("summary", "")),
                link=entry.get("link", ""),
                source=source,
                published=entry.get("published", ""),
            )
            for entry in parsed.entries
        ]