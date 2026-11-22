"""main.py - Start here. Run from the project root with:  python -m src.main

Exit codes: 0 = success, 1 = failed (worth retrying), 2 = config problem (retrying cannot help).
"""
import sys

from src.config_loader import ConfigError, load_config
from src.pipeline import run
from src.utils.logger import get_logger, setup_logging

EXIT_FAILED = 1
EXIT_CONFIG_PROBLEM = 2


def main() -> int:
    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"Config problem: {exc}")
        return EXIT_CONFIG_PROBLEM

    setup_logging(cfg.setting("logging.level", "INFO"))
    log = get_logger(__name__)
    try:
        run(cfg)
    except ConfigError as exc:
        log.error("Config problem: %s", exc)
        return EXIT_CONFIG_PROBLEM
    except Exception:
        log.exception("Pipeline failed")
        return EXIT_FAILED
    return 0


if __name__ == "__main__":
    sys.exit(main())