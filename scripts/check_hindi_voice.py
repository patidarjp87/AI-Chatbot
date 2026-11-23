"""check_hindi_voice.py - Tests the Hindi voices.

Run from the project root:   python scripts/check_hindi_voice.py
For each voice it saves a sample MP3 in output/ (listen to it) and shows whether the
service reports the time of EACH WORD. Synced captions need that.
"""
import asyncio
from collections import Counter
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
VOICES = ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]
TEXT = (
    "क्या आपके पास कभी किसी अनजान नंबर से कॉल आया है, जिसमें कहा गया कि आपका बैंक खाता बंद होने वाला है? "
    "घबराइए मत। असली बैंक कभी फोन पर आपसे OTP या पिन नहीं मांगता। "
    "अगर कोई मांगे, तो कॉल काट दीजिए और बैंक के आधिकारिक नंबर पर खुद संपर्क कीजिए।"
)
TICKS_PER_SECOND = 10_000_000  # edge-tts reports time in 100-nanosecond units


async def probe(voice: str) -> None:
    try:
        speech = edge_tts.Communicate(TEXT, voice, boundary="WordBoundary")
    except TypeError:  # older edge-tts versions have no 'boundary' option
        speech = edge_tts.Communicate(TEXT, voice)

    counts: Counter = Counter()
    samples = []
    last_end = 0.0
    out_path = OUTPUT_DIR / f"hindi_voice_test_{voice}.mp3"
    with out_path.open("wb") as audio_file:
        async for chunk in speech.stream():
            kind = chunk["type"]
            counts[kind] += 1
            if kind == "audio":
                audio_file.write(chunk["data"])
            else:
                start = chunk.get("offset", 0) / TICKS_PER_SECOND
                end = start + chunk.get("duration", 0) / TICKS_PER_SECOND
                last_end = max(last_end, end)
                if len(samples) < 4:
                    samples.append(f"{kind}: '{chunk.get('text', '')}' at {start:.2f}s")

    print(f"\n=== {voice} ===")
    print(f"Saved: {out_path}")
    print(f"Event counts: {dict(counts)}")
    print(f"Speech length (from timings): {last_end:.1f} s")
    for line in samples:
        print("  ", line)
    words_in_text = len(TEXT.split())
    word_events = counts.get("WordBoundary", 0)
    if word_events == 0:
        print(f"RESULT: no word timings (text has {words_in_text} words). Captions would use estimated timing.")
    else:
        print(f"RESULT: {word_events} word timings for {words_in_text} words. Good for synced captions.")


async def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    for voice in VOICES:
        try:
            await probe(voice)
        except Exception as exc:  # show the problem instead of stopping
            print(f"\n=== {voice} ===\nFAILED: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())