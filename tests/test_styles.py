"""Tests for the four display styles. Run: python3 -m pytest"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from render import auto_bars, colour_field  # noqa: E402
from styles import STYLES, draw, sample_levels  # noqa: E402

SIZES = [(64, 32), (64, 64), (128, 64)]
CYAN = (45, 226, 245)


def frame(style, w, h, levels=None, peaks=None, peak_colour=CYAN):
    n = auto_bars(w)
    if levels is None:
        levels, peaks = sample_levels(n)
    return np.asarray(draw(style, levels, peaks, w, h, colour_field("vapor", n, h), peak_colour))


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("w,h", SIZES)
def test_every_style_draws_at_every_size(style, w, h):
    px = frame(style, w, h)
    assert px.shape == (h, w, 3)
    assert px.any()


@pytest.mark.parametrize("style", STYLES)
def test_louder_lights_more(style):
    n = auto_bars(64)
    quiet = frame(style, 64, 64, np.full(n, 0.1), np.full(n, 0.1)).sum()
    loud = frame(style, 64, 64, np.full(n, 0.9), np.full(n, 0.9)).sum()
    assert loud > quiet


def test_unknown_style_falls_back_to_sunset():
    n = auto_bars(64)
    lv, pk = sample_levels(n)
    f = colour_field("vapor", n, 64)
    assert (np.asarray(draw("nonsense", lv, pk, 64, 64, f, CYAN))
            == np.asarray(draw("sunset", lv, pk, 64, 64, f, CYAN))).all()


def test_sunset_has_slits_and_a_floor():
    n = auto_bars(64)
    px = frame("sunset", 64, 64, np.full(n, 1.0), np.full(n, 1.0))
    horizon = round(64 * 0.8)
    lit_rows = [px[y].any() for y in range(horizon)]
    assert not all(lit_rows)                  # at least one slit cuts through full bars
    assert px[horizon + 1:].any()             # the grid floor is below the horizon


def test_meter_marks_the_peak_in_cyan():
    n = auto_bars(64)
    px = frame("meter", 64, 64, np.full(n, 0.3), np.full(n, 0.8))
    assert (px.reshape(-1, 3) == CYAN).all(axis=1).any()


def test_equals_reflection_sits_below_the_bars():
    n = auto_bars(64)
    px = frame("equals", 64, 64, np.full(n, 0.8), np.full(n, 0.8))
    bottom = px[48:]
    # the reflection is cyan-to-blue: blue channel dominates red
    assert bottom[..., 2].sum() > bottom[..., 0].sum()


def test_disc_is_centred():
    px = frame("disc", 128, 64)
    lit_x = np.nonzero(px.any(axis=(0, 2)))[0]
    assert abs((lit_x.min() + lit_x.max()) / 2 - 63.5) <= 2
