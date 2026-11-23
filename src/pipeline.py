"""pipeline.py - Runs the steps in order.

topic/news -> script -> voice -> footage -> video build -> upload
"""
import json
import re
from dataclasses import asdict
from pathlib import Path

from src.config_loader import Config, ConfigError
from src.footage import get_footage_provider
from src.news import get_news_provider
from src.script import get_script_provider
from src.upload import get_upload_provider
from src.utils.dates import today_string
from src.utils.logger import get_logger
from src.utils.paths import ensure_dir
from src.video.builder import build_video
from src.voice import get_voice_provider

log = get_logger(__name__)
TOTAL_STEPS = 6


def _slugify(text: str, max_length: int = 40) -> str:
    """'OTP Fraud Basics' -> 'otp-fraud-basics'. Keeps English letters and digits only (Hindi gives '')."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:max_length].strip("-")


def _make_run_folder(cfg: Config, script) -> Path:
    """Create the output folder for this run, named from output.filename_pattern."""
    slug = _slugify(script.slug) or _slugify(script.title) or "video"  # Hindi titles have no English letters
    pattern = cfg.setting("output.filename_pattern", "{date}_{slug}")
    name = pattern.format(date=today_string(cfg.setting("project.timezone")), slug=slug)
    return ensure_dir(Path(cfg.setting("output.dir", "output")) / name)


def _check_safety(cfg: Config) -> None:
    """Phase 1 topics are NOT source-verified, so they may only be uploaded privately."""
    if (
        cfg.setting("news.provider") == "evergreen"
        and cfg.setting("upload.provider") == "youtube"
        and str(cfg.setting("upload.youtube.mode", "private")).lower() != "private"
    ):
        raise ConfigError(
            "The 'evergreen' topic list is for testing and is not source-verified. "
            "Set upload.youtube.mode to 'private' (or use upload.provider: manual)."
        )


def run(cfg: Config) -> Path:
    """Run the whole pipeline once and return the output folder."""
    _check_safety(cfg)
    uploader = get_upload_provider(cfg)  # created first, so missing keys fail fast

    log.info("Step 1/%d: choosing the topic (%s)", TOTAL_STEPS, cfg.setting("news.provider"))
    news_items = get_news_provider(cfg).fetch()

    log.info("Step 2/%d: writing script (%s)", TOTAL_STEPS, cfg.setting("script.provider"))
    script = get_script_provider(cfg).generate(news_items)
    log.info("Script: %d scenes, %d words", len(script.scenes), script.word_count)

    run_dir = _make_run_folder(cfg, script)
    (run_dir / "script.json").write_text(
        json.dumps(script.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "news.json").write_text(
        json.dumps([asdict(item) for item in news_items], indent=2, ensure_ascii=False), encoding="utf-8"
    )

    log.info("Step 3/%d: creating voiceover (%s)", TOTAL_STEPS, cfg.setting("voice.provider"))
    voice = get_voice_provider(cfg).synthesize(script.voiceover_text, run_dir / "voiceover.mp3")
    _, _, max_seconds = cfg.video_size
    if voice.duration_seconds > max_seconds:
        log.warning("Voiceover is %.1fs, longer than the %ss limit", voice.duration_seconds, max_seconds)

    log.info("Step 4/%d: getting footage (%s)", TOTAL_STEPS, cfg.setting("footage.provider"))
    footage = get_footage_provider(cfg).fetch(script, run_dir)
    credits = sorted({clip.credit for clip in footage if clip.credit})
    if credits:  # credit the stock source and videographers in the description
        script.description += "\n\nStock footage: " + ", ".join(credits)
        (run_dir / "script.json").write_text(
            json.dumps(script.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    log.info("Step 5/%d: building video", TOTAL_STEPS)
    video_path = build_video(cfg, script, voice, footage, run_dir / "video.mp4")

    log.info("Step 6/%d: finishing (%s)", TOTAL_STEPS, cfg.setting("upload.provider"))
    uploader.publish(video_path, script)

    log.info("Done. Files are in: %s", run_dir)
    return run_dir