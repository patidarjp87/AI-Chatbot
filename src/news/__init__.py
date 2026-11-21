"""Picks the news provider named in settings.yaml (news.provider)."""
from src.config_loader import Config
from src.news.base import NewsProvider
from src.utils.registry import load_provider

# To add a provider: add one line here, then set news.provider in settings.yaml
_REGISTRY = {
    "rss": "src.news.rss_provider:RssNewsProvider",
}


def get_news_provider(cfg: Config) -> NewsProvider:
    return load_provider("news", cfg.setting("news.provider"), _REGISTRY)(cfg)