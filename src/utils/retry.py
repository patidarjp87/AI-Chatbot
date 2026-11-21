"""retry.py - Try again when something fails temporarily (network or API hiccups).

Use as a decorator:
    @retry(attempts=3, delay=2)
    def call_api(): ...

Pass giveup=function to stop at once for errors that can never succeed
(for example a wrong model name), instead of waiting through the retries.
"""
import functools
import time
from typing import Callable, Optional, Tuple, Type

from src.utils.logger import get_logger

log = get_logger(__name__)


def retry(
    attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    giveup: Optional[Callable[[Exception], bool]] = None,
) -> Callable:
    """Retry a function up to `attempts` times.

    delay      - seconds to wait before the first retry
    backoff    - multiplier applied to the wait after each failure (2 -> 2s, 4s, 8s)
    exceptions - only these error types trigger a retry
    giveup     - optional check; if it returns True the error is raised immediately
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if giveup is not None and giveup(exc):
                        log.error("%s failed and will not be retried: %s", func.__name__, exc)
                        raise
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