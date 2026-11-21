"""Picks the footage provider named in settings.yaml (footage.provider)."""
from src.config_loader import Config
from src.footage.base import FootageProvider
from src.utils.registry import load_provider

_REGISTRY = {
    "none": "src.footage.none_provider:NoFootageProvider",
    "pexels": "src.footage.pexels_provider:PexelsFootageProvider",  # next step
    "pixabay": "src.footage.pixabay_provider:PixabayFootageProvider",
}


def get_footage_provider(cfg: Config) -> FootageProvider:
    return load_provider("footage", cfg.setting("footage.provider"), _REGISTRY)(cfg)