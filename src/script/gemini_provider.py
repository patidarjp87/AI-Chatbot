"""gemini_provider.py - Writes the script and the scene plan with Google Gemini.

Settings (settings.yaml -> script.gemini): model, api_key_env, temperature.
The instructions for the AI live in config/prompts/*.txt, so you can change the
tone without touching any code.

One request returns everything as JSON: title, description, hashtags, layout and
scenes. We check the answer and ask again (up to MAX_ATTEMPTS) if it is invalid
or too long.
"""
from __future__ import annotations

import json
import re

from src.config_loader import Config, ConfigError
from src.models import NewsItem, Scene, VideoScript
from src.script.base import ScriptProvider
from src.utils.dates import today_string
from src.utils.logger import get_logger
from src.utils.paths import resolve
from src.utils.retry import retry

log = get_logger(__name__)

MAX_ATTEMPTS = 3            # how many times we ask Gemini for a valid script
_SUMMARY_CHARS = 300        # how much of each news summary we send to Gemini
_MIN_WORD_RATIO = 0.7       # the script should use at least 70% of the word budget
_YOUTUBE_TITLE_LIMIT = 100  # YouTube rejects longer titles


def word_limits(cfg: Config) -> tuple[int, int]:
    """Return (min_words, max_words) that fit the video length in settings.yaml."""
    rate = cfg.setting("script.speaking_rate_wpm", 150)
    _, _, max_seconds = cfg.video_size
    max_words = int(rate * max_seconds / 60 * 0.9)  # 10% safety margin
    return int(max_words * _MIN_WORD_RATIO), max_words


def _extract_json(raw: str) -> dict:
    """Pull the JSON object out of Gemini's answer, even if it added code fences."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in the answer")
    return json.loads(text[start:end + 1])


def _as_list(value) -> list:
    """Accept a list, a single string, or nothing, and always return a list."""
    if isinstance(value, list):
        return value
    return [value] if value else []


def parse_script(raw: str, cfg: Config) -> VideoScript:
    """Turn Gemini's JSON answer into a VideoScript. Raises ValueError if it is unusable."""
    data = _extract_json(raw)

    scenes_raw = data.get("scenes")
    if not isinstance(scenes_raw, list) or not scenes_raw:
        raise ValueError("'scenes' is missing or empty")

    scenes: list[Scene] = []
    for number, item in enumerate(scenes_raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"scene {number} is not an object")
        text = str(item.get("text", "")).strip()
        if not text:
            raise ValueError(f"scene {number} has no text")
        highlights = [str(w).strip() for w in _as_list(item.get("highlight_words")) if str(w).strip()]
        scenes.append(Scene(
            text=text,
            keyword=str(item.get("keyword", "")).strip(),
            on_screen_text=str(item.get("on_screen_text", "")).strip(),
            highlight_words=highlights[:3],
            presenter_moment=bool(item.get("presenter_moment", False)),
        ))

    # Hashtags: make sure each starts with '#', and add #Shorts for Shorts videos
    hashtags = []
    for tag in _as_list(data.get("hashtags")):
        tag = str(tag).strip().replace(" ", "")
        if tag:
            hashtags.append(tag if tag.startswith("#") else "#" + tag)
    if cfg.setting("video.format") == "shorts" and "#shorts" not in [h.lower() for h in hashtags]:
        hashtags.insert(0, "#Shorts")

    # Layout: only allow ones listed in style.yaml, otherwise use the default from settings
    allowed = cfg.style_value("allowed_layouts", ["default"])
    layout = str(data.get("layout", "")).strip()
    if layout not in allowed:
        layout = cfg.setting("video.layout", "default")

    date = today_string(cfg.setting("project.timezone"))
    title = str(data.get("title", "")).strip() or f"World News Update - {date}"
    return VideoScript(
        title=title[:_YOUTUBE_TITLE_LIMIT],
        description=str(data.get("description", "")).strip(),
        hashtags=hashtags,
        scenes=scenes,
        layout=layout,
    )


def fit_length(script: VideoScript, max_words: int) -> VideoScript:
    """If the script is too long, drop scenes (keeping the opening and the outro)."""
    while script.word_count > max_words and len(script.scenes) > 2:
        removed = script.scenes.pop(-2)
        log.warning("Script was too long. Dropped a scene: %s", removed.text[:60])
    return script


class GeminiScriptProvider(ScriptProvider):
    def __init__(self, cfg: Config):
        super().__init__(cfg)
        key = cfg.secret(cfg.setting("script.gemini.api_key_env", "GEMINI_API_KEY"))
        try:
            from google import genai  # imported here so 'sample' mode works without it
        except ImportError as exc:
            raise ConfigError("google-genai is not installed. Run: pip install -r requirements.txt") from exc

        self._model = cfg.setting("script.gemini.model")
        if not self._model:
            raise ConfigError("script.gemini.model is empty in settings.yaml")
        self._temperature = float(cfg.setting("script.gemini.temperature", 0.7))
        self._client = genai.Client(api_key=key)

    # ---------- building the request ----------
    def _read_prompt(self, setting_key: str) -> str:
        """Read a prompt text file whose path is set in settings.yaml."""
        path = resolve(self.cfg.setting(setting_key, ""))
        if not path.is_file():
            raise ConfigError(f"Prompt file not found: {path} (setting: {setting_key})")
        return path.read_text(encoding="utf-8").strip()

    def _build_prompt(self, news_items: list[NewsItem], min_words: int, max_words: int) -> str:
        """Combine the writing rules, the output format and today's news into one prompt."""
        text = self._read_prompt("script.script_prompt_file") + "\n\n" + self._read_prompt("script.scene_prompt_file")

        fillers = {
            "MIN_WORDS": min_words,
            "MAX_WORDS": max_words,
            "DATE": today_string(self.cfg.setting("project.timezone")),
            "LAYOUTS": ", ".join(self.cfg.style_value("allowed_layouts", ["default"])),
            "SCENE_MIN": self.cfg.setting("video.scene_seconds_min", 2),
            "SCENE_MAX": self.cfg.setting("video.scene_seconds_max", 4),
        }
        for name, value in fillers.items():
            text = text.replace(f"<<{name}>>", str(value))

        lines = []
        for number, item in enumerate(news_items, start=1):
            line = f"{number}. [{item.source}] {item.title}"
            if item.summary:
                line += f" - {item.summary[:_SUMMARY_CHARS]}"
            lines.append(line)
        return text + "\n\nNEWS ITEMS:\n" + "\n".join(lines)

    # ---------- calling Gemini ----------
    @retry(attempts=3, delay=5)
    def _call_model(self, prompt: str) -> str:
        """Send the prompt to Gemini and return the raw text answer."""
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": self._temperature},
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini returned an empty answer (it may have been blocked).")
        return text

    # ---------- the main method ----------
    def generate(self, news_items: list[NewsItem]) -> VideoScript:
        min_words, max_words = word_limits(self.cfg)
        prompt = self._build_prompt(news_items, min_words, max_words)
        log.info("Asking Gemini (%s) for a script of %d-%d words", self._model, min_words, max_words)

        feedback = ""
        too_long: VideoScript | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            raw = self._call_model(prompt + feedback)
            try:
                script = parse_script(raw, self.cfg)
            except ValueError as exc:
                log.warning("Attempt %d/%d: unusable answer (%s)", attempt, MAX_ATTEMPTS, exc)
                feedback = f"\n\nYour previous answer was invalid: {exc}. Return valid JSON exactly as specified."
                continue

            if script.word_count > max_words:
                log.warning("Attempt %d/%d: script has %d words (max %d)",
                            attempt, MAX_ATTEMPTS, script.word_count, max_words)
                too_long = script
                feedback = (f"\n\nYour previous script had {script.word_count} words. "
                            f"It must be at most {max_words}. Shorten it.")
                continue
            return script

        if too_long is not None:  # still too long after all attempts: trim it
            return fit_length(too_long, max_words)
        raise RuntimeError(f"Gemini did not return a usable script after {MAX_ATTEMPTS} attempts.")