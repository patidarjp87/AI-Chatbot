"""sample_provider.py - Builds a simple script from real headlines, with NO AI and NO key.

Used to test the whole pipeline. The Gemini provider replaces it later.
"""
import re

from src.models import NewsItem, Scene, VideoScript
from src.script.base import ScriptProvider
from src.utils.dates import today_string

# Common words we skip when making footage search keywords
_STOPWORDS = {
    "that", "this", "with", "from", "have", "will", "after", "over", "into", "says",
    "about", "their", "been", "were", "than", "they", "what", "when", "where", "which",
    "while", "would", "could", "your", "more", "also", "amid",
}

INTRO = "Here are today's top world headlines."
OUTRO = "That's your update. Follow for more."


def _keywords(text: str, limit: int = 3) -> list[str]:
    """Pick a few meaningful words from a headline (used to search stock footage)."""
    words = [w for w in re.findall(r"[A-Za-z']+", text) if len(w) > 3 and w.lower() not in _STOPWORDS]
    return words[:limit]


def _first_sentence(text: str, max_words: int = 25) -> str:
    """First sentence of a summary, or '' if missing or too long."""
    if not text:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    return sentence if len(sentence.split()) <= max_words else ""


def _with_period(text: str) -> str:
    text = text.strip()
    return text if text and text[-1] in ".!?" else text + "."


class SampleScriptProvider(ScriptProvider):
    def generate(self, news_items: list[NewsItem]) -> VideoScript:
        rate = self.cfg.setting("script.speaking_rate_wpm", 150)
        _, _, max_seconds = self.cfg.video_size
        # Words that fit in the video, with a 10% safety margin
        budget = int(rate * max_seconds / 60 * 0.9)

        scenes = [Scene(text=INTRO, keyword="news studio", on_screen_text="Today's Headlines")]
        used = len(INTRO.split()) + len(OUTRO.split())

        for item in news_items:
            title_line = _with_period(item.title)
            detail = _first_sentence(item.summary)
            # Try headline + detail first; fall back to the headline alone
            for line in (f"{title_line} {detail}".strip(), title_line):
                words = len(line.split())
                if used + words <= budget:
                    keys = _keywords(item.title)
                    scenes.append(Scene(
                        text=line,
                        keyword=" ".join(keys),
                        on_screen_text=" ".join(item.title.split()[:8]),
                        highlight_words=keys[:2],
                    ))
                    used += words
                    break
            else:
                break  # nothing more fits in the video length

        scenes.append(Scene(text=OUTRO, keyword="city skyline", on_screen_text="Follow for more"))

        date = today_string(self.cfg.setting("project.timezone"))
        sources = sorted({item.source for item in news_items if item.source})
        return VideoScript(
            title=f"Top World Headlines - {date}",
            description="Your daily world news update.\n\nSources: " + ", ".join(sources),
            hashtags=["#Shorts", "#News", "#WorldNews"],
            scenes=scenes,
            layout=self.cfg.setting("video.layout", "default"),
        )