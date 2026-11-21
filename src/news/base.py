"""base.py (news) - The rules every news provider must follow."""
from abc import ABC, abstractmethod

from src.config_loader import Config
from src.models import NewsItem


class NewsProvider(ABC):
    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abstractmethod
    def fetch(self) -> list[NewsItem]:
        """Return today's news stories, newest and most relevant first."""