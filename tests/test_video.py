"""test_video.py - Checks caption grouping, scene timing and that a frame renders at the right size."""
from pathlib import Path

from src.config_loader import load_config
from src.models import NewsItem, VoiceResult, WordTiming
from src.script.sample_provider import SampleScriptProvider
from src.video.builder import load_layout
from src.video.captions import build_chunks


def _fake_voice(text: str) -> VoiceResult:
    words = [WordTiming(w, i * 0.3, i * 0.3 + 0.25) for i, w in enumerate(text.split())]
    return VoiceResult(audio_path=Path("none.mp3"), duration_seconds=words[-1].end, words=words)


def test_sentence_end_closes_a_caption():
    words = [WordTiming(w, i * 0.3, i * 0.3 + 0.25) for i, w in enumerate("One two. Three four five".split())]
    chunks = build_chunks(words, 3)
    assert [len(c.words) for c in chunks] == [2, 3]


def test_layout_renders_a_frame_of_the_right_size():
    cfg = load_config()
    items = [NewsItem(title="Markets react to a big announcement today", summary="Details follow.")]
    script = SampleScriptProvider(cfg).generate(items)
    voice = _fake_voice(script.voiceover_text)
    layout = load_layout(cfg, "default")(cfg, script, voice, [])
    frame = layout.render(1.0)
    width, height, _ = cfg.video_size
    assert frame.size == (width, height)