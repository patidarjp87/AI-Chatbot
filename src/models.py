"""models.py - The data shapes passed between steps.

news step   -> list[NewsItem]
script step -> VideoScript (made of Scene objects)
voice step  -> VoiceResult (audio file + word timings)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class NewsItem:
    """One news story from a feed."""
    title: str
    summary: str = ""
    link: str = ""
    source: str = ""
    published: str = ""


@dataclass
class Scene:
    """One visual moment in the video, with the line spoken during it."""
    text: str                                   # words spoken during this scene
    keyword: str = ""                           # search term for stock footage
    on_screen_text: str = ""                    # big text shown on screen
    highlight_words: list[str] = field(default_factory=list)  # accent-colored words
    presenter_moment: bool = False              # later phase: presenter cut-in here


@dataclass
class VideoScript:
    """The full script plus the plan for what appears on screen."""
    title: str
    description: str
    hashtags: list[str]
    scenes: list[Scene]
    layout: str = "default"

    @property
    def voiceover_text(self) -> str:
        """All scene lines joined into the text the voice will read."""
        return " ".join(scene.text.strip() for scene in self.scenes)

    @property
    def word_count(self) -> int:
        return len(self.voiceover_text.split())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WordTiming:
    """When one spoken word starts and ends (in seconds). Used for captions later."""
    text: str
    start: float
    end: float


@dataclass
class VoiceResult:
    """What the voice step returns."""
    audio_path: Path
    duration_seconds: float
    words: list[WordTiming]


@dataclass
class FootageClip:
    """A stock clip chosen for one scene (used when footage.provider is not 'none')."""
    scene_index: int
    path: Path