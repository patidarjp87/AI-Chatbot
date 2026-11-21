"""base.py (footage) - The rules every footage provider must follow."""
from abc import ABC, abstractmethod
from pathlib import Path

from src.config_loader import Config
from src.models import FootageClip, VideoScript


class FootageProvider(ABC):
    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abstractmethod
    def fetch(self, script: VideoScript, work_dir: Path) -> list[FootageClip]:
        """Return one clip per scene where footage was found (can be fewer, or none)."""