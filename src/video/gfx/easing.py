"""easing.py - Animation maths.

Every animation is a pure function of time: the same time always gives the same picture,
so frames can be rendered in any order (or one at a time) with identical results.
"""
from __future__ import annotations

import math


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def progress(t: float, start: float, duration: float) -> float:
    """0..1 progress of something that starts at `start` seconds and lasts `duration` seconds."""
    if duration <= 0:
        return 1.0 if t >= start else 0.0
    return clamp01((t - start) / duration)


def lerp(a: float, b: float, x: float) -> float:
    """Value between a and b (x=0 gives a, x=1 gives b)."""
    return a + (b - a) * x


def _out_back(x: float) -> float:
    c1 = 1.70158  # a small overshoot, then settle
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


EASINGS = {
    "linear": lambda x: x,
    "in_cubic": lambda x: x ** 3,
    "out_quad": lambda x: 1 - (1 - x) ** 2,
    "out_cubic": lambda x: 1 - (1 - x) ** 3,
    "in_out_cubic": lambda x: 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2,
    "in_out_sine": lambda x: -(math.cos(math.pi * x) - 1) / 2,
    "out_back": _out_back,
}


def ease(name: str, x: float) -> float:
    """Apply a named easing curve to a 0..1 value."""
    function = EASINGS.get(name)
    if function is None:
        raise ValueError(f"Unknown easing '{name}'. Available: {', '.join(EASINGS)}")
    return function(clamp01(x))


def pulse(t: float, period: float, amount: float) -> float:
    """A gentle repeating size change for emphasis: swings between 1.0 and 1.0 + amount."""
    if period <= 0:
        return 1.0
    return 1.0 + amount * (0.5 - 0.5 * math.cos(2 * math.pi * t / period))