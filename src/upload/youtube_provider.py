"""youtube_provider.py - Uploads the finished video to YouTube.

Settings (settings.yaml -> upload.youtube):
  mode                      private | scheduled | public
  publish_delay_hours       used by 'scheduled' mode
  category_id               25 = News & Politics
  made_for_kids             must be declared; news is normally false
  contains_synthetic_media  true adds YouTube's "altered or synthetic content" label
  notify_subscribers        whether subscribers are notified
  *_env                     names of the environment variables that hold the login values

Modes:
  private    - uploaded private. You publish it yourself in YouTube Studio.
  scheduled  - uploaded private WITH a publish time. YouTube makes it public by itself
               at that time. You can edit or delete it in Studio before then.
  public     - published immediately (no review).

While your Google API project is unverified, YouTube may keep API uploads private
whatever the mode says. The log shows what YouTube actually did.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from src.config_loader import Config, ConfigError
from src.models import VideoScript
from src.upload.base import UploadProvider
from src.utils.logger import get_logger

log = get_logger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
MODES = ("private", "scheduled", "public")
TITLE_LIMIT = 100                # YouTube's title limit (characters)
DESCRIPTION_LIMIT_BYTES = 4900   # YouTube allows 5000 bytes
TAGS_LIMIT_CHARS = 450           # YouTube allows 500 characters of tags in total
CHUNK_BYTES = 8 * 1024 * 1024    # upload in 8 MB pieces

_HINTS = {
    "quotaExceeded": "The daily YouTube API quota is used up. It resets at midnight Pacific Time.",
    "uploadLimitExceeded": "YouTube's upload limit for this channel was reached. Try again later.",
    "youtubeSignupRequired": "This Google account has no YouTube channel yet.",
    "insufficientPermissions": "The login lacks upload permission. Run scripts/youtube_login.py again.",
}


def _clean(text: str, max_bytes: int) -> str:
    """Remove the characters YouTube rejects (< and >) and cut to a byte limit."""
    text = text.replace("<", "").replace(">", "").strip()
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text
    return data[:max_bytes].decode("utf-8", errors="ignore").rstrip()


def _tags(hashtags: list[str]) -> list[str]:
    """Turn '#WorldNews' into the tag 'WorldNews', within YouTube's total length limit."""
    tags: list[str] = []
    total = 0
    for hashtag in hashtags:
        name = re.sub(r"\W", "", hashtag.lstrip("#"))
        if not name or name.lower() in {t.lower() for t in tags}:
            continue
        if total + len(name) + 1 > TAGS_LIMIT_CHARS:
            break
        tags.append(name)
        total += len(name) + 1
    return tags


def build_body(
    script: VideoScript,
    *,
    mode: str,
    delay_hours: float,
    category_id: str,
    language: str,
    made_for_kids: bool,
    synthetic: bool,
    now: datetime,
) -> dict:
    """Build the request that describes the video (title, description, visibility...)."""
    if mode not in MODES:
        raise ConfigError(f"upload.youtube.mode must be one of {', '.join(MODES)} (got '{mode}')")
    if mode == "scheduled" and delay_hours <= 0:
        raise ConfigError("upload.youtube.publish_delay_hours must be greater than 0")

    description = _clean(f"{script.description}\n\n{' '.join(script.hashtags)}", DESCRIPTION_LIMIT_BYTES)
    snippet = {
        "title": _clean(script.title, 400)[:TITLE_LIMIT] or "Daily news update",
        "description": description,
        "categoryId": str(category_id),
        "defaultLanguage": language,
        "defaultAudioLanguage": language,
    }
    tags = _tags(script.hashtags)
    if tags:
        snippet["tags"] = tags

    status = {
        # A scheduled video must be private until its publish time
        "privacyStatus": "public" if mode == "public" else "private",
        "selfDeclaredMadeForKids": made_for_kids,
        "containsSyntheticMedia": synthetic,
    }
    if mode == "scheduled":
        publish_time = (now + timedelta(hours=delay_hours)).astimezone(timezone.utc)
        status["publishAt"] = publish_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"snippet": snippet, "status": status}


def _describe_http_error(exc: HttpError) -> str:
    """A readable explanation of a YouTube API error."""
    content = exc.content.decode("utf-8", errors="replace") if isinstance(exc.content, bytes) else str(exc.content)
    text = f"HTTP {getattr(exc.resp, 'status', '?')}: {exc.reason}"
    for key, hint in _HINTS.items():
        if key in content:
            return f"{text}. {hint}"
    return text


class YouTubeUploadProvider(UploadProvider):
    def __init__(self, cfg: Config):
        super().__init__(cfg)
        prefix = "upload.youtube."
        self._mode = str(cfg.setting(prefix + "mode", "private")).lower()
        if self._mode not in MODES:
            raise ConfigError(f"upload.youtube.mode must be one of {', '.join(MODES)} (got '{self._mode}')")
        self._delay_hours = float(cfg.setting(prefix + "publish_delay_hours", 3))
        self._category_id = str(cfg.setting(prefix + "category_id", "25"))
        self._made_for_kids = bool(cfg.setting(prefix + "made_for_kids", False))
        self._synthetic = bool(cfg.setting(prefix + "contains_synthetic_media", False))
        self._notify = bool(cfg.setting(prefix + "notify_subscribers", False))
        self._language = cfg.setting("project.language", "en")

        # Read the login values now, so a missing one stops the run immediately
        self._credentials = Credentials(
            token=None,  # an access token is requested automatically from the refresh token
            refresh_token=cfg.secret(cfg.setting(prefix + "refresh_token_env", "YOUTUBE_REFRESH_TOKEN")),
            token_uri=TOKEN_URI,
            client_id=cfg.secret(cfg.setting(prefix + "client_id_env", "YOUTUBE_CLIENT_ID")),
            client_secret=cfg.secret(cfg.setting(prefix + "client_secret_env", "YOUTUBE_CLIENT_SECRET")),
            scopes=SCOPES,
        )

    def publish(self, video_path: Path, script: VideoScript) -> None:
        body = build_body(
            script,
            mode=self._mode,
            delay_hours=self._delay_hours,
            category_id=self._category_id,
            language=self._language,
            made_for_kids=self._made_for_kids,
            synthetic=self._synthetic,
            now=datetime.now(timezone.utc),
        )
        size_mb = video_path.stat().st_size / 1_048_576
        log.info("Uploading %s (%.1f MB) to YouTube in '%s' mode", video_path.name, size_mb, self._mode)
        if self._mode == "scheduled":
            log.info("Planned publish time: %s UTC", body["status"]["publishAt"])

        try:
            response = self._upload(video_path, body)
        except RefreshError as exc:
            raise ConfigError(
                "The YouTube login expired or was revoked. Run: python scripts/youtube_login.py, "
                "then update the 3 YOUTUBE_ values in .env and in GitHub Secrets."
            ) from exc
        except HttpError as exc:
            raise RuntimeError(f"YouTube rejected the upload: {_describe_http_error(exc)}") from exc
        self._report(response, video_path.parent)

    def _upload(self, video_path: Path, body: dict) -> dict:
        """Send the file to YouTube in pieces and return YouTube's answer."""
        youtube = build("youtube", "v3", credentials=self._credentials, cache_discovery=False)
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=CHUNK_BYTES, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media, notifySubscribers=self._notify
        )
        response = None
        while response is None:
            progress, response = request.next_chunk(num_retries=4)  # retries on temporary errors
            if progress:
                log.info("  upload %d%%", int(progress.progress() * 100))
        return response

    def _report(self, response: dict, out_dir: Path) -> None:
        """Log what YouTube did and save the details next to the video."""
        video_id = response.get("id")
        if not video_id:
            raise RuntimeError(f"YouTube did not return a video ID. Answer: {response}")
        status = response.get("status", {})
        privacy = status.get("privacyStatus")
        publish_at = status.get("publishAt")

        log.info("Uploaded! Video ID: %s", video_id)
        log.info("Review or edit it here: https://studio.youtube.com/video/%s/edit", video_id)
        log.info("YouTube reports: privacy=%s, publishAt=%s", privacy, publish_at or "(none)")
        if self._mode == "scheduled" and not publish_at:
            log.warning(
                "The video is private and has NO publish time. YouTube may keep API uploads private "
                "until your API project passes Google's audit. Publish it by hand in YouTube Studio."
            )
        elif self._mode == "public" and privacy != "public":
            log.warning("You asked for public, but YouTube made it '%s'. Publish it by hand in Studio.", privacy)

        details = {
            "video_id": video_id,
            "watch_url": f"https://youtu.be/{video_id}",
            "studio_url": f"https://studio.youtube.com/video/{video_id}/edit",
            "mode": self._mode,
            "privacy_status": privacy,
            "publish_at": publish_at,
        }
        (out_dir / "youtube_upload.json").write_text(json.dumps(details, indent=2), encoding="utf-8")