"""pixabay_provider.py - Finds and downloads free stock videos from Pixabay, one per scene.

Settings (settings.yaml -> footage.pixabay): api_key_env, quality, max_file_mb,
min_seconds, cache_dir.
For every scene:
  1. search Pixabay using the scene's keyword (then shorter versions if nothing is found)
  2. pick a clip we haven't used yet, in a size that is good enough
  3. download it once into the cache folder
A scene with no clip simply keeps the animated grid background.

Pixabay asks API users to cache results for 24 hours, so search answers are saved
in the cache folder and reused. Clips are downloaded, not linked to.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

from src.config_loader import Config, ConfigError
from src.footage.base import FootageProvider
from src.models import FootageClip, VideoScript
from src.utils.logger import get_logger
from src.utils.paths import ensure_dir
from src.utils.retry import retry

log = get_logger(__name__)

SEARCH_URL = "https://pixabay.com/api/videos/"
RESULTS_PER_SEARCH = 20
SEARCH_CACHE_SECONDS = 24 * 60 * 60   # reuse the same search for 24 hours
MAX_QUERY_CHARS = 100                  # Pixabay's limit for the search text
_SIZE_ORDER = ["large", "medium", "small", "tiny"]


class _RateLimited(Exception):
    """Pixabay said we sent too many requests."""


class _NetworkError(Exception):
    """A connection problem. The message never contains the URL, because the URL holds our key."""


def query_variants(query: str) -> list[str]:
    """'oil refinery night' -> ['oil refinery night', 'oil refinery', 'oil'] (broader searches)."""
    words = query.split()
    variants = [query.strip()[:MAX_QUERY_CHARS]]
    if len(words) > 2:
        variants.append(" ".join(words[:2]))
    if len(words) > 1:
        variants.append(words[0])
    return list(dict.fromkeys(v for v in variants if v))


def pick_file(hit: dict, preferred: str, max_bytes: int) -> str | None:
    """Choose which size of a video to download.

    Starts at the preferred size and moves to smaller ones if a size is missing
    or the file is bigger than max_bytes.
    """
    sizes = hit.get("videos") or {}
    start = _SIZE_ORDER.index(preferred) if preferred in _SIZE_ORDER else 0
    for name in _SIZE_ORDER[start:]:
        info = sizes.get(name) or {}
        size = info.get("size") or 0
        if info.get("url") and info.get("width") and (not size or size <= max_bytes):
            return info["url"]
    return None


class PixabayFootageProvider(FootageProvider):
    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self._key = cfg.secret(cfg.setting("footage.pixabay.api_key_env", "PIXABAY_API_KEY"))
        self._quality = cfg.setting("footage.pixabay.quality", "large")
        self._max_bytes = int(float(cfg.setting("footage.pixabay.max_file_mb", 60)) * 1024 * 1024)
        self._min_seconds = float(cfg.setting("footage.pixabay.min_seconds", 4))
        self._cache_dir = ensure_dir(cfg.setting("footage.pixabay.cache_dir", "tmp/footage"))

    def fetch(self, script: VideoScript, work_dir: Path) -> list[FootageClip]:
        clips: list[FootageClip] = []
        used_ids: set[int] = set()
        for index, scene in enumerate(script.scenes):
            query = scene.keyword.strip()
            if not query:
                continue
            try:
                clip = self._find_clip(index, query, used_ids)
            except ConfigError:
                raise  # a bad key should stop the run, not be skipped
            except _RateLimited:
                log.warning("Pixabay rate limit reached. Remaining scenes use the plain background.")
                break
            except Exception as exc:  # one failed scene should not stop the video
                log.warning("Scene %d: no footage (%s)", index + 1, exc)
                continue
            if clip:
                clips.append(clip)
            else:
                log.info("Scene %d: nothing found for '%s'", index + 1, query)
        log.info("Footage found for %d of %d scenes", len(clips), len(script.scenes))
        return clips

    def _find_clip(self, index: int, query: str, used_ids: set[int]) -> FootageClip | None:
        """Try the keyword, then broader versions, until a usable unused clip turns up."""
        for text in query_variants(query):
            for hit in self._search(text):
                if hit["id"] in used_ids or (hit.get("duration") or 0) < self._min_seconds:
                    continue
                link = pick_file(hit, self._quality, self._max_bytes)
                if not link:
                    continue
                used_ids.add(hit["id"])
                path = self._download(hit["id"], link)
                log.info("Scene %d: '%s' -> Pixabay video %s", index + 1, text, hit["id"])
                user = hit.get("user")
                return FootageClip(scene_index=index, path=path,
                                   credit=f"{user} (Pixabay)" if user else "Pixabay")
        return None

    # ---------- searching (with a 24-hour cache) ----------
    def _search(self, query: str) -> list[dict]:
        name = hashlib.sha256(query.lower().encode("utf-8")).hexdigest()[:16]
        cache_file = self._cache_dir / f"pixabay_search_{name}.json"
        if cache_file.exists() and time.time() - cache_file.stat().st_mtime < SEARCH_CACHE_SECONDS:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        hits = self._request(query)
        cache_file.write_text(json.dumps(hits), encoding="utf-8")
        return hits

    @retry(attempts=3, delay=2, exceptions=(_NetworkError,))
    def _request(self, query: str) -> list[dict]:
        try:
            response = requests.get(
                SEARCH_URL,
                params={
                    "key": self._key, "q": query, "video_type": "film",
                    "safesearch": "true", "per_page": RESULTS_PER_SEARCH,
                },
                timeout=20,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            # Raise our own error: requests' message would include the URL, and the URL has the key
            raise _NetworkError(f"could not reach Pixabay ({type(exc).__name__})") from None
        if response.status_code == 429:
            raise _RateLimited()
        if response.status_code in (400, 401, 403):
            raise ConfigError(
                f"Pixabay answered with HTTP {response.status_code}. "
                f"Check PIXABAY_API_KEY in your .env file. Details: {response.text[:120]}"
            )
        if response.status_code != 200:  # a temporary server problem: skip this scene
            raise RuntimeError(f"Pixabay answered with HTTP {response.status_code}")
        return response.json().get("hits", [])

    # ---------- downloading ----------
    @retry(attempts=3, delay=2, exceptions=(requests.RequestException,))
    def _download(self, video_id: int, link: str) -> Path:
        """Download a clip once. Later runs reuse the saved copy."""
        path = self._cache_dir / f"pixabay_{video_id}.mp4"
        if path.exists() and path.stat().st_size > 0:
            return path
        partial = path.with_suffix(".part")  # avoids keeping a half-downloaded file
        with requests.get(link, stream=True, timeout=60) as response:
            response.raise_for_status()
            with partial.open("wb") as file:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    file.write(chunk)
        partial.replace(path)
        return path