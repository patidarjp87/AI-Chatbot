"""base.py (upload) - The rules every upload provider must follow."""
from abc import ABC, abstractmethod
from pathlib import Path

from src.config_loader import Config
from src.models import VideoScript


class UploadProvider(ABC):
    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abstractmethod
    def publish(self, video_path: Path, script: VideoScript) -> None:
        """Do something with the finished video (save it, upload it, ...)."""