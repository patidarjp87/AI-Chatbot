"""registry.py - Finds the provider class named in settings.yaml.

Each step keeps a small table like {"rss": "src.news.rss_provider:RssNewsProvider"}.
This helper loads the right class only when it's needed, and gives a clear
message if a provider isn't built yet.
"""
import importlib

from src.config_loader import ConfigError


def load_provider(step: str, name: str | None, registry: dict[str, str]):
    """Return the provider CLASS for `name`, or raise a readable ConfigError."""
    if not name or name not in registry:
        available = ", ".join(sorted(registry))
        raise ConfigError(f"Unknown {step} provider '{name}'. Available: {available}")

    module_name, class_name = registry[name].split(":")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigError(f"Could not load {step} provider '{name}': {exc}") from exc

    provider_class = getattr(module, class_name, None)
    if provider_class is None:
        raise ConfigError(
            f"The {step} provider '{name}' is not implemented yet "
            f"({module_name} has no class {class_name})."
        )
    return provider_class