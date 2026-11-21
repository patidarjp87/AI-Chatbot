"""Picks the upload provider named in settings.yaml (upload.provider)."""
from src.config_loader import Config
from src.upload.base import UploadProvider
from src.utils.registry import load_provider

_REGISTRY = {
    "manual": "src.upload.manual_provider:ManualUploadProvider",
    "youtube": "src.upload.youtube_provider:YouTubeUploadProvider",  # later phase
}


def get_upload_provider(cfg: Config) -> UploadProvider:
    return load_provider("upload", cfg.setting("upload.provider"), _REGISTRY)(cfg)