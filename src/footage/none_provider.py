"""none_provider.py - No stock footage. The layout draws its own animated background."""
from pathlib import Path

from src.footage.base import FootageProvider
from src.models import FootageClip, VideoScript


class NoFootageProvider(FootageProvider):
    def fetch(self, script: VideoScript, work_dir: Path) -> list[FootageClip]:
        return []