"""edge_provider.py - Free voiceover using Microsoft Edge's voices (edge-tts).

Voice, speed and pitch come from settings.yaml (voice.edge).
Also records WHEN each word is spoken, so captions can match the voice later.
"""
import asyncio
from pathlib import Path

import edge_tts

from src.models import VoiceResult, WordTiming
from src.utils.logger import get_logger
from src.utils.retry import retry
from src.voice.base import VoiceProvider

log = get_logger(__name__)

_TICKS_PER_SECOND = 10_000_000   # edge-tts reports time in 100-nanosecond units
_FALLBACK_BYTES_PER_SECOND = 6000  # default edge audio is 48 kbit/s


class EdgeVoiceProvider(VoiceProvider):
    def synthesize(self, text: str, out_path: Path) -> VoiceResult:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        return self._synthesize_with_retry(text, out_path)

    @retry(attempts=3, delay=3)
    def _synthesize_with_retry(self, text: str, out_path: Path) -> VoiceResult:
        return asyncio.run(self._stream(text, out_path))

    async def _stream(self, text: str, out_path: Path) -> VoiceResult:
        voice = self.cfg.setting("voice.edge.voice_name", "en-US-GuyNeural")
        rate = self.cfg.setting("voice.edge.rate", "+0%")
        pitch = self.cfg.setting("voice.edge.pitch", "+0Hz")

        try:  # newer edge-tts versions need word timings requested explicitly
            speech = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
        except TypeError:  # older versions don't have this option
            speech = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)

        words: list[WordTiming] = []
        last_end = 0.0
        audio_bytes = 0
        with out_path.open("wb") as audio_file:
            async for chunk in speech.stream():
                if chunk["type"] == "audio":
                    audio_file.write(chunk["data"])
                    audio_bytes += len(chunk["data"])
                elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                    start = chunk["offset"] / _TICKS_PER_SECOND
                    end = start + chunk["duration"] / _TICKS_PER_SECOND
                    last_end = max(last_end, end)
                    if chunk["type"] == "WordBoundary":
                        words.append(WordTiming(text=chunk["text"], start=start, end=end))

        if audio_bytes == 0:
            raise RuntimeError("Voice service returned no audio")

        duration = last_end or audio_bytes / _FALLBACK_BYTES_PER_SECOND
        if not words:  # service gave no word timings: spread words evenly
            words = _estimate_words(text, duration)
        log.info("Voiceover ready: %.1fs, %d words, voice %s", duration, len(words), voice)
        return VoiceResult(audio_path=out_path, duration_seconds=duration, words=words)


def _estimate_words(text: str, duration: float) -> list[WordTiming]:
    """Rough word timings, based on word length, when real ones aren't available."""
    tokens = text.split()
    total_chars = sum(len(token) for token in tokens) or 1
    timings, cursor = [], 0.0
    for token in tokens:
        length = duration * len(token) / total_chars
        timings.append(WordTiming(text=token, start=cursor, end=cursor + length))
        cursor += length
    return timings