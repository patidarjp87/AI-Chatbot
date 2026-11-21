"""base.py (voice) - The rules every voice provider must follow."""
from abc import ABC, abstractmethod
from pathlib import Path

from src.config_loader import Config
from src.models import VoiceResult


class VoiceProvider(ABC):
    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abstractmethod
    def synthesize(self, text: str, out_path: Path) -> VoiceResult:
        """Create an audio file from text and return its length and word timings."""