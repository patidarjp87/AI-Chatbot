"""Picks the voice provider named in settings.yaml (voice.provider)."""
from src.config_loader import Config
from src.utils.registry import load_provider
from src.voice.base import VoiceProvider

_REGISTRY = {
    "edge": "src.voice.edge_provider:EdgeVoiceProvider",
    "elevenlabs": "src.voice.elevenlabs_provider:ElevenLabsVoiceProvider",  # later phase
    "recorded": "src.voice.recorded_provider:RecordedVoiceProvider",        # later phase
}


def get_voice_provider(cfg: Config) -> VoiceProvider:
    return load_provider("voice", cfg.setting("voice.provider"), _REGISTRY)(cfg)