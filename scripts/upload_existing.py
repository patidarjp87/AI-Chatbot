"""upload_existing.py - Upload a video you already made, without rebuilding it.

Run from the project root:
    python scripts/upload_existing.py                  # uses the newest folder in output/
    python scripts/upload_existing.py output/FOLDER    # uses a specific folder
It uses the upload settings in config/settings.yaml (upload.provider and upload.youtube.*).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # lets this script import the src package

from src.config_loader import ConfigError, load_config  # noqa: E402
from src.models import Scene, VideoScript  # noqa: E402
from src.upload import get_upload_provider  # noqa: E402
from src.utils.logger import setup_logging  # noqa: E402


def newest_run_folder(output_dir: Path) -> Path:
    """The most recently changed folder that contains a video.mp4."""
    folders = [p for p in output_dir.iterdir() if p.is_dir() and (p / "video.mp4").exists()]
    if not folders:
        raise SystemExit(f"No folder with a video.mp4 found in {output_dir}")
    return max(folders, key=lambda p: p.stat().st_mtime)


def load_script(path: Path) -> VideoScript:
    """Rebuild the script object from the script.json saved next to the video."""
    data = json.loads(path.read_text(encoding="utf-8"))
    scenes = [Scene(**scene) for scene in data.pop("scenes")]
    return VideoScript(scenes=scenes, **data)


def main() -> int:
    try:
        cfg = load_config()
        setup_logging(cfg.setting("logging.level", "INFO"))
        if len(sys.argv) > 1:
            folder = Path(sys.argv[1]).resolve()
        else:
            folder = newest_run_folder(ROOT / cfg.setting("output.dir", "output"))
        print(f"Using: {folder}")
        script = load_script(folder / "script.json")
        get_upload_provider(cfg).publish(folder / "video.mp4", script)
    except ConfigError as exc:
        print(f"Config problem: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())