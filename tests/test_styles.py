"""Tests for the four display styles. Run: python3 -m pytest"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from render import auto_bars, colour_field  # noqa: E402
from styles import STYLES, draw, sample_levels  # noqa: E402

SIZES = [(64, 32), (32, 64), (64, 64), (128, 64), (64, 128)]   # width x height; 32x64 and 64x128 are upright
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


# A needle swings rather than lights more; Dance arrows take a moment to
# climb into view. Both have their own tests below.
@pytest.mark.parametrize("style", [s for s in STYLES if s not in ("vu", "dance")])
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


def lit_centre_x(px, rows):
    xs = np.nonzero(px[rows].sum(axis=2).max(axis=0) > 150)[0]
    return xs.mean()


def test_needle_swings_right_when_louder():
    # A needle doesn't light more as it gets louder: it moves to the right.
    n = auto_bars(64)
    quiet = frame("vu", 64, 64, np.full(n, 0.1), np.full(n, 0.1))
    loud = frame("vu", 64, 64, np.full(n, 0.9), np.full(n, 0.9))
    rows = slice(24, 39)                       # only the needle: below the scale, above the hub
    assert lit_centre_x(loud, rows) > lit_centre_x(quiet, rows) + 10


def test_wide_needle_has_two_meters():
    n = auto_bars(128)
    levels = np.r_[np.full(n // 2, 0.9), np.full(n - n // 2, 0.1)]   # loud bass only
    px = frame("vu", 128, 64, levels, levels)
    rows = slice(24, 39)
    assert lit_centre_x(px[:, :64], rows) > lit_centre_x(px[:, 64:], rows) + 10


def test_mirror_is_symmetric():
    n = auto_bars(64)
    lv, pk = sample_levels(n)
    px = frame("mirror", 64, 64, lv, pk).astype(int)
    assert (px[:32] == px[32:][::-1]).all()


def test_waterfall_scrolls_down():
    from styles import WATERFALL_EVERY, _falls
    _falls.clear()
    n = auto_bars(64)
    loud, quiet = np.full(n, 0.9), np.zeros(n)
    for _ in range(WATERFALL_EVERY):
        frame("waterfall", 64, 64, loud, loud)
    for _ in range(WATERFALL_EVERY * 4):
        px = frame("waterfall", 64, 64, quiet, quiet)
    lit = px.sum(axis=(1, 2))
    assert lit[0] < lit[4] and lit[4] > 0     # the loud moment has moved down 4 rows


def test_waterfall_still_has_something_to_show():
    from styles import _falls
    _falls.clear()
    n = auto_bars(64)
    lv, pk = sample_levels(n)
    px = np.asarray(draw("waterfall", lv, pk, 64, 64, colour_field("ocean", n, 64), None, still=True))
    assert (px.sum(axis=(1, 2)) > 0).mean() > 0.9   # nearly every row lit
    assert not _falls                          # and the real history is untouched


@pytest.mark.parametrize("theme", ["fire", "ocean", "forest", "aurora", "amber", "mono", "pastel", "thermal"])
def test_new_themes_get_brighter_upwards(theme):
    f = colour_field(theme, 16, 64)
    assert f.shape == (64, 16, 3)
    assert f[-1].sum() > f[0].sum()


@pytest.mark.parametrize("w,h", SIZES)
def test_needle_fits_and_is_centred(w, h):
    px = frame("vu", w, h)
    lit = np.nonzero(px.any(axis=2))
    assert lit[0].min() >= 0 and lit[0].max() < h
    top, bottom = lit[0].min(), lit[0].max()
    assert abs((top + bottom) / 2 - (h - 1) / 2) <= h * 0.12   # roughly centred top to bottom


@pytest.mark.parametrize("cfg,want", [
    ({"rows": "32", "columns": "64"}, (64, 32, 0)),
    ({"rows": "32", "columns": "64", "rotate": "90"}, (32, 64, 90)),
    ({"rows": "64", "columns": "64", "chain_length": "2"}, (128, 64, 0)),
    ({"rows": "64", "columns": "64", "chain_length": "2", "rotate": "270"}, (64, 128, 270)),
    ({"rows": "64", "columns": "64", "rotate": "45"}, (64, 64, 0)),        # nonsense -> not turned
])
def test_panel_geometry(cfg, want):
    from display_logic import panel_geometry
    assert panel_geometry(cfg) == want


def test_scope_holds_a_steady_note_still():
    # The scope starts each picture where the wave crosses zero going up, so
    # a steady note looks the same from one picture to the next.
    n = auto_bars(64)
    f = colour_field("ocean", n, 64)
    sr, hz = 48000, 440
    pics = []
    for start in (0, 1234, 5555):                    # three moments, out of step with the note
        t = (np.arange(2048) + start) / sr
        pics.append(np.asarray(draw("scope", np.full(n, .5), np.full(n, .5), 64, 64, f, None,
                                    wave=np.sin(2 * np.pi * hz * t))))
    lit = [p.sum(axis=2) > 0 for p in pics]
    assert (lit[0] == lit[1]).mean() > 0.98 and (lit[0] == lit[2]).mean() > 0.98


def test_trails_remember_and_fade():
    from styles import _trails
    _trails.clear()
    n = auto_bars(64)
    f = colour_field("fire", n, 64)
    loud, quiet = np.full(n, 0.9), np.zeros(n)
    first = np.asarray(draw("trails", loud, loud, 64, 64, f, None)).sum()
    after = [np.asarray(draw("trails", quiet, quiet, 64, 64, f, None)).sum() for _ in range(8)]
    assert 0 < after[0] < first                       # the loud moment lingers...
    assert after[-1] < after[0]                       # ...and fades away


def test_plasma_is_brighter_when_louder():
    from styles import draw_plasma
    n = auto_bars(64)
    f = colour_field("aurora", n, 64)
    quiet = np.asarray(draw_plasma(np.full(n, .05), None, 64, 64, f, None, t=3.0)).sum()
    loud = np.asarray(draw_plasma(np.full(n, .9), None, 64, 64, f, None, t=3.0)).sum()
    assert loud > quiet * 1.5


def test_this_pis_own_settings_win(tmp_path):
    from display_logic import panel_config_paths, read_panel_config
    (tmp_path / "rgb_options.ini").write_text(
        "[DEFAULT]\nrows = 64\ncolumns = 64\nhardware_mapping = adafruit-hat\ngpio_slowdown = 2\n")
    d = read_panel_config(panel_config_paths(str(tmp_path)))
    assert d["hardware_mapping"] == "adafruit-hat"                 # no local file: the defaults
    (tmp_path / "rgb_options.local.ini").write_text(
        "[DEFAULT]\nhardware_mapping = adafruit-hat-pwm\ngpio_slowdown = 4\n")
    d = read_panel_config(panel_config_paths(str(tmp_path)))
    assert (d["hardware_mapping"], d["gpio_slowdown"], d["rows"]) == ("adafruit-hat-pwm", "4", "64")


def test_dance_finds_the_beat_and_lands_arrows_on_it():
    # A kick every half second (120 beats a minute): the tracker should find
    # the beat, and arrows planned from then on should land on kicks.
    from styles import DANCE_TRAVEL_S, _dance, draw_dance
    _dance.clear()
    n = auto_bars(64)
    f = colour_field("rainbow", n, 64)
    quiet = np.zeros(n)
    kick = np.r_[np.full(n // 4, 0.9), np.zeros(n - n // 4)]
    dt = 1 / 40
    for k in range(int(8 / dt)):                              # 8 seconds
        draw_dance(kick if k % 20 == 0 else quiet, quiet, 64, 64, f, None, dt=dt)
    st = next(iter(_dance.values()))
    assert st.beat.period and abs(st.beat.period - 0.5) < 0.02
    on_beat = [when for _, when, strength in st.arrows if strength >= 1.0]
    assert on_beat, "on-beat arrows are on their way"
    for when in on_beat:                                      # each lands on a kick (multiples of 0.5 s)
        assert abs(((when + dt / 2) % 0.5) - dt / 2) < 2 * dt + 1e-9
    assert all(when - st.t <= DANCE_TRAVEL_S + 1e-9 for _, when, _ in st.arrows)


def test_dance_finds_the_beat_in_real_sound():
    # The demo track (120 bpm) through the real analyser: a bass line that
    # keeps the low bars near the top mustn't hide the kicks.
    from audio_source import DemoSource
    from styles import _dance, draw
    from spectrum import Analyzer, BarSmoother
    _dance.clear()
    demo, n, dt = DemoSource(), auto_bars(64), 1 / 40
    f = colour_field("rainbow", n, 64)
    an, sm = Analyzer(demo.samplerate, n, 2048), BarSmoother(n)
    for k in range(int(6 / dt)):
        wave = demo.read(2048, now=1 + k * dt)
        levels, peaks = sm.update(an.process(wave, 50, dt), dt)
        draw("dance", levels, peaks, 64, 64, f, None, wave=wave, dt=dt)
    st = next(iter(_dance.values()))
    assert st.beat.period and abs(st.beat.period - 0.5) < 0.02
    on_beat = [when + 1 for _, when, strength in st.arrows if strength >= 1.0]
    assert on_beat
    for when in on_beat:                                      # within 60 ms after a kick
        assert (when % 0.5) < 0.06 or (when % 0.5) > 0.49


def test_dance_shows_arrows_climbing_after_music_starts():
    from styles import _dance, draw_dance
    _dance.clear()
    n = auto_bars(64)
    f = colour_field("rainbow", n, 64)
    quiet = np.zeros(n)
    first = np.asarray(draw_dance(quiet, quiet, 64, 64, f, None)).sum()
    loud = np.r_[np.full(n // 4, 0.9), np.zeros(n - n // 4)]
    for k in range(30):
        px = np.asarray(draw_dance(loud if k % 10 == 0 else quiet, quiet, 64, 64, f, None))
    assert px.sum() > first                                   # arrows on the way up


def test_dance_eight_lanes_and_round_arrows():
    from styles import _arrow, draw_dance
    n = auto_bars(64)
    f = colour_field("rainbow", n, 64)
    lv, pk = sample_levels(n)
    four = np.asarray(draw_dance(lv, pk, 64, 64, f, None, still=True, lanes_n=4))
    eight = np.asarray(draw_dance(lv, pk, 64, 64, f, None, still=True, lanes_n=8))
    assert not (four == eight).all()
    narrow = np.asarray(draw_dance(lv, pk, 32, 32, colour_field("rainbow", 8, 32), None, still=True, lanes_n=8))
    assert narrow.any()                                       # too narrow for 8: falls back to 4
    fill, _ = _arrow(15, "N")
    assert not fill[0, 0] and not fill[0, -1]                 # corners empty
    assert fill[1:4, 7].any()                                 # the tip is there
    ne, _ = _arrow(15, "NE")
    head, tail = ne[:7, 8:].sum(), ne[8:, :7].sum()
    assert head > tail and ne[:3, -4:].any()                  # points up and right: tip in that corner


def test_arrows_match_in_every_direction():
    from styles import DANCE_LANES, _arrow
    for size in (7, 9, 11, 15, 21):
        lit = [int(_arrow(size, d)[0].sum()) for d in DANCE_LANES[8]]
        assert max(lit) <= min(lit) * 1.2, (size, lit)       # same weight whichever way it points


def test_every_style_is_in_exactly_one_group():
    from styles import STYLE_GROUPS
    grouped = [st for _, members in STYLE_GROUPS for st in members]
    assert sorted(grouped) == sorted(STYLES)
