"""preview_graphics.py - Draws the motion-graphics components to PICTURES so you can check the look.

Run from the project root:
    python scripts/preview_graphics.py            (all samples)
    python scripts/preview_graphics.py --guides   (also draws the safe-area rectangle)
Saves into output/preview/: for each sample, a full-size picture of the final moment and a
contact sheet showing six moments of the animation. The sample texts are for previews only.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from src.config_loader import load_config  # noqa: E402
from src.utils.logger import setup_logging  # noqa: E402
from src.video.gfx.components import get_component  # noqa: E402
from src.video.gfx.layers import GridBackground  # noqa: E402
from src.video.gfx.theme import Theme  # noqa: E402

SAMPLES = {
    "title": ("title_reveal", {
        "kicker": "डिजिटल समझ", "title": "UPI पेमेंट कैसे काम करता है?", "highlight": ["UPI"]}),
    "card_info": ("information_card", {
        "tone": "cyan", "title": "UPI क्या है?", "value": "तुरंत पेमेंट",
        "text": "मोबाइल ऐप से एक बैंक खाते से दूसरे बैंक खाते में पैसे भेजने का तरीका।"}),
    "card_danger": ("information_card", {
        "tone": "danger", "title": "सावधान", "value": "अनजान लिंक? रुकें!",
        "text": "किसी अनजान व्यक्ति के कहने पर अपना यूपीआई पिन न डालें।"}),
    "card_long_text": ("information_card", {
        "tone": "warning", "title": "लंबा टेक्स्ट टेस्ट",
        "value": "यह एक काफी लंबा वाक्य है जो कार्ड में फिट होना चाहिए",
        "text": "यह जांचने के लिए है कि बहुत लंबा विवरण भी कार्ड के अंदर बिना कटे और बिना एक-दूसरे पर चढ़े दिखता है या नहीं। "
                "अगर जरूरत हो तो अक्षर अपने आप थोड़े छोटे हो जाने चाहिए।"}),
}
TIMES = [0.0, 0.2, 0.4, 0.7, 1.2, 3.0]
DURATION = 4.0
THUMB_WIDTH = 270


def main() -> int:
    guides = "--guides" in sys.argv
    cfg = load_config()
    setup_logging("INFO")
    theme = Theme.from_config(cfg)
    background = GridBackground(theme)
    left, top, right, bottom = theme.safe
    box = (left, top, theme.width - left - right, theme.height - top - bottom)

    out_dir = ROOT / "output" / "preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    thumb_h = round(THUMB_WIDTH * theme.height / theme.width)

    for name, (visual_type, spec) in SAMPLES.items():
        component = get_component(visual_type)(theme, spec, box)

        def render(t: float) -> Image.Image:
            frame = background.frame(t)
            component.draw(frame, t, DURATION)
            return frame

        sheet = Image.new("RGB", (len(TIMES) * (THUMB_WIDTH + 10) + 10, thumb_h + 40), (24, 24, 24))
        for i, t in enumerate(TIMES):
            thumb = render(t).resize((THUMB_WIDTH, thumb_h), Image.Resampling.LANCZOS)
            x = 10 + i * (THUMB_WIDTH + 10)
            sheet.paste(thumb, (x, 30))
            ImageDraw.Draw(sheet).text((x, 8), f"t = {t:.1f}s", fill=(220, 220, 220))
        sheet.save(out_dir / f"{name}_sheet.png")

        final = render(TIMES[-1])
        if guides:
            ImageDraw.Draw(final).rectangle([box[0], box[1], box[0] + box[2], box[1] + box[3]],
                                            outline=(255, 80, 80), width=3)
        final.save(out_dir / f"{name}_final.png")

        start = time.perf_counter()
        for i in range(30):
            render(i / 30)
        per_frame = (time.perf_counter() - start) / 30 * 1000
        extra = f", text scale {component.fit_scale}" if hasattr(component, "fit_scale") else ""
        print(f"{name}: saved pictures; about {per_frame:.0f} ms per frame{extra}")

    print(f"\nOpen the pictures in: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())