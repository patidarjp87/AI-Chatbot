"""main.py - Start here. Run from the project root with:  python -m src.main"""
import sys

from src.config_loader import ConfigError, load_config
from src.pipeline import run
from src.utils.logger import get_logger, setup_logging


def main() -> int:
    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"Config problem: {exc}")
        return 1

    setup_logging(cfg.setting("logging.level", "INFO"))
    log = get_logger(__name__)
    try:
        run(cfg)
    except ConfigError as exc:
        log.error("Config problem: %s", exc)
        return 1
    except Exception:
        log.exception("Pipeline failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())