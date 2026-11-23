"""test_gfx_foundation.py - Checks the animation maths, theme, text pictures and first components. Offline."""
import pytest
from PIL import Image, ImageChops

from src.config_loader import Config, ConfigError, load_config
from src.utils.drawing import text_layer
from src.video.gfx.components import get_component
from src.video.gfx.components.information_card import InformationCard
from src.video.gfx.components.title_reveal import TitleReveal
from src.video.gfx.easing import EASINGS, ease, progress
from src.video.gfx.layers import GridBackground
from src.video.gfx.theme import Theme


def _theme() -> Theme:
    return Theme.from_config(load_config())


def _box(theme: Theme):
    left, top, right, bottom = theme.safe
    return (left, top, theme.width - left - right, theme.height - top - bottom)


def test_every_easing_starts_at_zero_and_ends_at_one():
    for name in EASINGS:
        assert ease(name, 0.0) == pytest.approx(0.0, abs=1e-9)
        assert ease(name, 1.0) == pytest.approx(1.0, abs=1e-9)


def test_progress_is_clamped():
    assert progress(-1, 0, 2) == 0
    assert progress(1, 0, 2) == 0.5
    assert progress(9, 0, 2) == 1
    assert progress(0.1, 0.5, 0) == 0


def test_bad_colour_in_style_gives_a_clear_error():
    settings = {"video": {"format": "shorts", "formats": {"shorts": {"width": 1080, "height": 1920, "max_seconds": 59}}}}
    cfg = Config(settings=settings, style={"theme": {"colors": {"cyan": "not-a-colour"}}})
    with pytest.raises(ConfigError):
        Theme.from_config(cfg)


def test_safe_area_leaves_room_in_the_frame():
    theme = _theme()
    left, top, right, bottom = theme.safe
    assert left + right < theme.width and top + bottom < theme.height


def test_text_layer_is_a_visible_rgba_picture_for_hindi():
    theme = _theme()
    layer, (dx, dy) = text_layer("स्कैम", theme.font("heading", "title"), (255, 255, 255))
    assert layer.mode == "RGBA"
    assert layer.getchannel("A").getbbox() is not None


def test_title_needs_a_title():
    with pytest.raises(ValueError):
        TitleReveal.validate({})


def test_card_needs_a_value_or_text_and_limits_length():
    with pytest.raises(ValueError):
        InformationCard.validate({"title": "x"})
    with pytest.raises(ValueError):
        InformationCard.validate({"text": "x" * 500})


def test_unknown_visual_type_is_rejected():
    with pytest.raises(ValueError):
        get_component("does_not_exist")


def test_same_time_gives_the_same_picture_in_any_order():
    theme = _theme()
    background = GridBackground(theme)
    component = TitleReveal(theme, {"title": "UPI पेमेंट कैसे काम करता है?", "highlight": ["UPI"]}, _box(theme))

    def render(t):
        frame = background.frame(t)
        component.draw(frame, t, 4.0)
        return frame

    first = render(1.0)
    render(0.2)
    render(2.5)
    again = render(1.0)
    assert ImageChops.difference(first, again).getbbox() is None


def test_components_draw_something_and_keep_the_frame_size():
    theme = _theme()
    background = GridBackground(theme)
    component = InformationCard(theme, {"tone": "danger", "title": "सावधान", "value": "रुकें!", "text": "सावधान रहें।"},
                                _box(theme))
    before = background.frame(3.0)
    after = before.copy()
    component.draw(after, 3.0, 4.0)
    assert after.size == (theme.width, theme.height)
    assert ImageChops.difference(before, after).getbbox() is not None


def test_long_card_text_fits_inside_its_box():
    theme = _theme()
    box = (60, 200, 900, 800)
    long_text = "यह बहुत लंबा विवरण है। " * 6
    card = InformationCard(theme, {"title": "टेस्ट", "value": "लंबा वाक्य जो कार्ड में फिट होना चाहिए", "text": long_text[:160]}, box)
    assert card.card_height <= box[3]