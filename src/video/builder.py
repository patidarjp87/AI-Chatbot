"""builder.py - Renders every frame with the chosen layout and sends it to FFmpeg,
together with the voiceover (and background music, if enabled in style.yaml).
"""
from __future__ import annotations

import importlib
import math
import shutil
import subprocess
from pathlib import Path

from src.config_loader import Config, ConfigError
from src.models import FootageClip, VideoScript, VoiceResult
from src.utils.logger import get_logger
from src.utils.paths import resolve

log = get_logger(__name__)

_TAIL_SECONDS = 0.4  # keep the picture a moment after the voice ends


def ffmpeg_path() -> str:
    """Use FFmpeg from the computer if installed, otherwise the bundled copy."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise RuntimeError("FFmpeg not found. Run: pip install -r requirements.txt") from exc


def load_layout(cfg: Config, name: str):
    """Find the layout class named in settings.yaml (video.layout)."""
    allowed = cfg.style_value("allowed_layouts", ["default"])
    if name not in allowed:
        raise ConfigError(f"Layout '{name}' is not in style.yaml allowed_layouts: {allowed}")
    try:
        module = importlib.import_module(f"src.video.layouts.{name}")
    except ImportError as exc:
        raise ConfigError(f"Could not load layout '{name}': {exc}") from exc
    return module.Layout


def build_video(
    cfg: Config, script: VideoScript, voice: VoiceResult, footage: list[FootageClip], out_path: Path
) -> Path:
    """Create the final MP4 and return its path."""
    width, height, _ = cfg.video_size
    fps = cfg.setting("video.fps", 30)
    layout = load_layout(cfg, script.layout)(cfg, script, voice, footage)

    total_seconds = voice.duration_seconds + _TAIL_SECONDS
    frame_count = math.ceil(total_seconds * fps)

    cmd = [
        ffmpeg_path(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-i", str(voice.audio_path),
    ]

    music_file = resolve(cfg.style_value("music.file", "assets/music/background.mp3"))
    use_music = cfg.style_value("music.enabled", False)
    if use_music and not music_file.exists():
        log.warning("Music enabled but file not found: %s. Continuing without music.", music_file)
        use_music = False

    if use_music:
        volume = cfg.style_value("music.volume", 0.12)
        # Loop the music, mix it quietly under the voice, then restore overall loudness
        mix = f"[2:a]volume={volume}[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0,volume=2[a]"
        cmd += ["-stream_loop", "-1", "-i", str(music_file), "-filter_complex", mix, "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]

    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total_seconds:.2f}", "-movflags", "+faststart", str(out_path),
    ]

    log.info("Rendering %d frames (%dx%d at %d fps)...", frame_count, width, height, fps)
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    step = max(1, frame_count // 10)
    try:
        for i in range(frame_count):
            process.stdin.write(layout.render(i / fps).tobytes())
            if i % step == 0:
                log.info("  %d%%", round(100 * i / frame_count))
        process.stdin.close()
    except BrokenPipeError:
        pass  # FFmpeg stopped early; its error message is read below
    finally:
        close = getattr(layout, "close", None)  # layouts can release clip readers here
        if close:
            close()

    error_text = process.stderr.read().decode(errors="replace")
    if process.wait() != 0:
        raise RuntimeError(f"FFmpeg failed:\n{error_text}")
    log.info("Video saved: %s", out_path)
    return out_path