"""test_gemini_fallback.py - Checks the model fallback logic with a fake Gemini. No internet needed."""
import pytest

from src.script.gemini_provider import GeminiScriptProvider


class FakeApiError(Exception):
    """Pretends to be Google's error, which carries an HTTP code."""
    def __init__(self, code):
        super().__init__(f"error {code}")
        self.code = code


def make_provider(outcomes):
    """A provider whose models answer (or fail) as listed in `outcomes`."""
    provider = GeminiScriptProvider.__new__(GeminiScriptProvider)  # skip the real setup
    provider._models = list(outcomes)
    provider._attempts = 1
    provider._retry_delay = 0
    calls = []

    def fake_call(model, prompt):
        calls.append(model)
        result = outcomes[model]
        if isinstance(result, Exception):
            raise result
        return result

    provider._call_one_model = fake_call
    return provider, calls


def test_moves_to_next_model_when_first_is_busy():
    provider, calls = make_provider({"m1": FakeApiError(503), "m2": "answer"})
    assert provider._call_model("prompt") == "answer"
    assert calls == ["m1", "m2"]


def test_moves_to_next_model_when_first_is_missing():
    provider, calls = make_provider({"m1": FakeApiError(404), "m2": "answer"})
    assert provider._call_model("prompt") == "answer"


def test_bad_key_stops_at_once():
    provider, calls = make_provider({"m1": FakeApiError(400), "m2": "answer"})
    with pytest.raises(FakeApiError):
        provider._call_model("prompt")
    assert calls == ["m1"]  # the second model was never tried


def test_all_models_failing_gives_clear_error():
    provider, _ = make_provider({"m1": FakeApiError(503), "m2": FakeApiError(503)})
    with pytest.raises(RuntimeError, match="All Gemini models failed"):
        provider._call_model("prompt")