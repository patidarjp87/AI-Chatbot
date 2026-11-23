"""check_hindi_text.py - Checks that Hindi (Devanagari) text draws correctly with a font.

Run from the project root and give one or more font files:
    python scripts/check_hindi_text.py assets/fonts/Hind-Bold.ttf assets/fonts/Poppins-Bold.ttf
It saves one picture per font into output/ and says whether Pillow can shape
complex scripts. Open each picture and look for:
  - empty boxes instead of letters (the font has no Hindi)
  - letters that do not join properly, for example क्ष ज्ञ श्र स्कैम द्वारा
"""
import sys
from pathlib import Path

import PIL
from PIL import Image, ImageDraw, ImageFont, features

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
LINES = [
    "डिजिटल समझ",
    "UPI स्कैम से सावधान रहें",
    "OTP किसी को न बताएं",
    "क्ष   त्र   ज्ञ   श्र   द्वारा   स्कैम",
    "साइबर सुरक्षा के आसान तरीके",
]
FONT_SIZE = 72
LINE_HEIGHT = 130


def main() -> int:
    if len(sys.argv) < 2:
        print("Give at least one font file, for example:")
        print("  python scripts/check_hindi_text.py assets/fonts/Hind-Bold.ttf")
        return 2

    raqm = features.check("raqm")
    print(f"Pillow version: {PIL.__version__}")
    print(f"Complex text layout (raqm) available: {raqm}")
    if not raqm:
        print("  -> Hindi letters may not join correctly. Send me this output.")
    engine = ImageFont.Layout.RAQM if raqm else ImageFont.Layout.BASIC

    OUTPUT_DIR.mkdir(exist_ok=True)
    for font_arg in sys.argv[1:]:
        font_path = Path(font_arg)
        if not font_path.is_absolute():
            font_path = ROOT / font_path
        if not font_path.exists():
            print(f"Font not found: {font_path}")
            continue
        font = ImageFont.truetype(str(font_path), FONT_SIZE, layout_engine=engine)
        image = Image.new("RGB", (1080, LINE_HEIGHT * len(LINES) + 60), (11, 15, 20))
        draw = ImageDraw.Draw(image)
        for i, line in enumerate(LINES):
            draw.text((40, 30 + i * LINE_HEIGHT), line, font=font, fill=(255, 255, 255))
        out = OUTPUT_DIR / f"hindi_font_test_{font_path.stem}.png"
        image.save(out)
        print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())