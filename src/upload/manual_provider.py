"""manual_provider.py - Does not upload. You review, edit and post the video yourself."""
from pathlib import Path

from src.models import VideoScript
from src.upload.base import UploadProvider
from src.utils.logger import get_logger

log = get_logger(__name__)


class ManualUploadProvider(UploadProvider):
    def publish(self, video_path: Path, script: VideoScript) -> None:
        log.info("Video saved for manual review: %s", video_path)
        log.info("Suggested title: %s", script.title)
        log.info("Hashtags: %s", " ".join(script.hashtags))