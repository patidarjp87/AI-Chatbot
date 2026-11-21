"""clips.py - Reads frames from a stock clip one after another, using FFmpeg.

The clip is scaled and cropped to fill the screen, and loops if the scene is
longer than the clip.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image


class ClipReader:
    def __init__(self, path: Path, size: tuple[int, int], fps: int, ffmpeg: str):
        width, height = size
        self.size = size
        self._frame_bytes = width * height * 3  # RGB: 3 bytes per pixel
        command = [
            ffmpeg, "-loglevel", "error",
            "-stream_loop", "-1", "-i", str(path),   # loop forever; we stop it ourselves
            "-an",                                   # ignore the clip's own audio
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                   f"crop={width}:{height},fps={fps}",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ]
        self._process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def next_frame(self) -> Image.Image | None:
        """Return the next frame, or None if the clip can't be read."""
        data = self._process.stdout.read(self._frame_bytes)
        if len(data) < self._frame_bytes:
            return None
        return Image.frombytes("RGB", self.size, data)

    def close(self) -> None:
        """Stop FFmpeg and free the pipe."""
        if self._process.poll() is None:
            self._process.kill()
        self._process.stdout.close()
        self._process.wait()