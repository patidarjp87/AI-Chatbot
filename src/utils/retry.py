"""retry.py - Try again when something fails temporarily (network or API hiccups).

Use as a decorator:
    @retry(attempts=3, delay=2)
    def call_api(): ...
"""
import functools
import time
from typing import Callable, Tuple, Type

from src.utils.logger import get_logger

log = get_logger(__name__)


def retry(
    attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """Retry a function up to `attempts` times.

    delay   - seconds to wait before the first retry
    backoff - multiplier applied to the wait after each failure (2 -> 2s, 4s, 8s)
    exceptions - only these error types trigger a retry
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == attempts:
                        log.error("%s failed after %d attempts: %s", func.__name__, attempts, exc)
                        raise  # give up and show the real error
                    log.warning(
                        "%s failed (attempt %d/%d): %s. Retrying in %.0fs",
                        func.__name__, attempt, attempts, exc, wait,
                    )
                    time.sleep(wait)
                    wait *= backoff

        return wrapper

    return decorator