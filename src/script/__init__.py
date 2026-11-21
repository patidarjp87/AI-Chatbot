"""Picks the script provider named in settings.yaml (script.provider)."""
from src.config_loader import Config
from src.script.base import ScriptProvider
from src.utils.registry import load_provider

_REGISTRY = {
    "sample": "src.script.sample_provider:SampleScriptProvider",
    "gemini": "src.script.gemini_provider:GeminiScriptProvider",  # next steps
}


def get_script_provider(cfg: Config) -> ScriptProvider:
    return load_provider("script", cfg.setting("script.provider"), _REGISTRY)(cfg)