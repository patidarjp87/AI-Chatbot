"""dates.py - Today's date in the timezone from settings.yaml (project.timezone)."""
from datetime import datetime


def today_string(timezone_name: str | None = None, fmt: str = "%Y-%m-%d") -> str:
    """Return today's date as text. Falls back to computer time if the timezone is unknown."""
    try:
        if timezone_name:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(timezone_name)).strftime(fmt)
    except Exception:
        pass  # unknown timezone (e.g. no tz database on Windows): use local time
    return datetime.now().strftime(fmt)