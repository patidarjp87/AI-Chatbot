"""base.py (script) - The rules every script provider must follow."""
from abc import ABC, abstractmethod

from src.config_loader import Config
from src.models import NewsItem, VideoScript


class ScriptProvider(ABC):
    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abstractmethod
    def generate(self, news_items: list[NewsItem]) -> VideoScript:
        """Turn news items into a voiceover script and a scene plan."""