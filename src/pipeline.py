"""pipeline.py - Runs the steps in order. New steps get added here as we build them.

news -> script -> voice -> footage -> video build -> upload
"""
import json
import re
from pathlib import Path
from dataclasses import asdict

from src.config_loader import Config
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
    """'Top World Headlines - 2026-11-22' -> 'top-world-headlines-2026-11-22'"""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:max_length]


def _make_run_folder(cfg: Config, title: str) -> Path:
    """Create the output folder for this run, named from output.filename_pattern."""
    pattern = cfg.setting("output.filename_pattern", "{date}_{slug}")
    name = pattern.format(date=today_string(cfg.setting("project.timezone")), slug=_slugify(title))
    return ensure_dir(Path(cfg.setting("output.dir", "output")) / name)


def run(cfg: Config) -> Path:
    """Run the whole pipeline once and return the output folder."""
    log.info("Step 1/%d: fetching news (%s)", TOTAL_STEPS, cfg.setting("news.provider"))
    news_items = get_news_provider(cfg).fetch()

    log.info("Step 2/%d: writing script (%s)", TOTAL_STEPS, cfg.setting("script.provider"))
    script = get_script_provider(cfg).generate(news_items)
    log.info("Script: %d scenes, %d words", len(script.scenes), script.word_count)

    run_dir = _make_run_folder(cfg, script.title)
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

    log.info("Step 5/%d: building video", TOTAL_STEPS)
    video_path = build_video(cfg, script, voice, footage, run_dir / "video.mp4")

    log.info("Step 6/%d: finishing (%s)", TOTAL_STEPS, cfg.setting("upload.provider"))
    get_upload_provider(cfg).publish(video_path, script)

    log.info("Done. Files are in: %s", run_dir)
    return run_dir