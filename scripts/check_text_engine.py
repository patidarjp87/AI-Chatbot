"""check_text_engine.py - Tests the new Hindi text engine and saves a picture to look at.

Run from the project root, giving one or more font files:
    python scripts/check_text_engine.py assets/fonts/Hind-Bold.ttf assets/fonts/Poppins-Bold.ttf
Look at each picture in output/. CORRECT looks like this:
  - "डिजिटल": the ि sign sits to the LEFT of ड and of ज
  - क्ष  त्र  ज्ञ  श्र : each is ONE joined shape, with no visible half-letter or dot
  - द्वारा and स्कैम : the first letter joins smoothly into the next
  - no empty boxes (a box means the font has no glyph for that character)
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import freetype
    import uharfbuzz
    from PIL import Image
    from src.utils.text_engine import HarfBuzzFont
except ImportError as exc:
    raise SystemExit(f"A package is missing: {exc}\nRun:  pip install uharfbuzz freetype-py")

OUTPUT_DIR = ROOT / "output"
LINES = [
    "डिजिटल समझ",
    "UPI स्कैम से सावधान रहें",
    "OTP किसी को न बताएं",
    "क्ष   त्र   ज्ञ   श्र   द्वारा   स्कैम",
    "₹5,000 का फ्रॉड। सावधान रहें! 2026",
    "Digital Samajh",
]
FONT_SIZE = 72
LINE_HEIGHT = 130


def main() -> int:
    if len(sys.argv) < 2:
        print("Give at least one font file, for example:")
        print("  python scripts/check_text_engine.py assets/fonts/Hind-Bold.ttf")
        return 2

    print(f"uharfbuzz version: {getattr(uharfbuzz, '__version__', '?')}")
    try:
        print(f"FreeType version: {freetype.version()}")
    except Exception:
        pass

    OUTPUT_DIR.mkdir(exist_ok=True)
    for font_arg in sys.argv[1:]:
        font_path = Path(font_arg)
        if not font_path.is_absolute():
            font_path = ROOT / font_path
        font = HarfBuzzFont(font_path, FONT_SIZE)

        image = Image.new("RGB", (1080, LINE_HEIGHT * len(LINES) + 40), (11, 15, 20))
        for i, line in enumerate(LINES):
            y = 20 + LINE_HEIGHT * i + LINE_HEIGHT / 2
            font.draw_text(image, (40, y), line, fill=(255, 255, 255), anchor="lm",
                           stroke_width=4, stroke_fill=(0, 0, 0))
        out = OUTPUT_DIR / f"hindi_engine_test_{font_path.stem}.png"
        image.save(out)

        # Speed: the first draw of a text is slower, repeats are cached (captions repeat across frames)
        sample = LINES[1]
        start = time.perf_counter()
        font.draw_text(image, (40, 60), sample, fill=(255, 255, 255), anchor="lm", stroke_width=4)
        first_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        for _ in range(200):
            font.draw_text(image, (40, 60), sample, fill=(255, 255, 255), anchor="lm", stroke_width=4)
        repeat_ms = (time.perf_counter() - start) * 1000 / 200

        print(f"\n{font_path.name}: saved {out}")
        print(f"  width of '{sample}': {font.getlength(sample):.0f} px")
        print(f"  first draw: {first_ms:.1f} ms, repeat draw: {repeat_ms:.2f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())