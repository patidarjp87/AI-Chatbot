"""logger.py - Readable progress and error messages.

Use in any file:
    from src.utils.logger import get_logger
    log = get_logger(__name__)
    log.info("Something happened")
"""
import logging
import sys

_configured = False  # makes sure we only set up logging once


def setup_logging(level: str = "INFO") -> None:
    """Call once at startup. The level comes from settings.yaml (logging.level)."""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger for one file. Pass __name__ so messages show where they came from."""
    return logging.getLogger(name)