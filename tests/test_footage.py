"""test_footage.py - Checks how we choose Pixabay sizes and search terms. Works offline."""
from src.footage.pixabay_provider import pick_file, query_variants


def _hit(**sizes):
    """Build a fake Pixabay result. Example: _hit(large=(1920, 10), medium=(1280, 5))"""
    return {"videos": {name: {"url": f"https://x/{name}.mp4", "width": w, "size": s}
                       for name, (w, s) in sizes.items()}}


def test_uses_preferred_size_when_available():
    assert pick_file(_hit(large=(1920, 10), medium=(1280, 5)), "large", 100) == "https://x/large.mp4"


def test_falls_back_to_a_smaller_size_when_the_file_is_too_big():
    assert pick_file(_hit(large=(1920, 500), medium=(1280, 50)), "large", 100) == "https://x/medium.mp4"


def test_skips_sizes_without_a_url():
    hit = {"videos": {"large": {"url": "", "width": 0, "size": 0},
                      "medium": {"url": "https://x/m.mp4", "width": 1280, "size": 5}}}
    assert pick_file(hit, "large", 100) == "https://x/m.mp4"


def test_returns_none_when_nothing_is_usable():
    assert pick_file({"videos": {}}, "large", 100) is None


def test_query_variants_get_broader():
    assert query_variants("oil refinery night") == ["oil refinery night", "oil refinery", "oil"]
    assert query_variants("city") == ["city"]