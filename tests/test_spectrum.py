"""Tests for the sound -> bar-heights maths and the drawing. Run: python3 -m pytest"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from audio_source import DemoSource, SoundDetector  # noqa: E402
from render import THEMES, album_palette, auto_bars, bar_layout, render  # noqa: E402
from spectrum import Analyzer, BarSmoother, band_bins  # noqa: E402

SR = 48000


def tone(freq, amp=0.5, n=2048, sr=SR):
    return (amp * np.sin(2 * np.pi * freq * np.arange(n) / sr)).astype(np.float32)


@pytest.mark.parametrize("n_bars", [4, 8, 16, 32, 64])
def test_bands_never_overlap_or_go_empty(n_bars):
    starts, ends, centres = band_bins(SR, 2048, n_bars)
    assert len(starts) == n_bars
    assert np.all(ends > starts)                  # every band has at least one bin
    assert np.all(starts[1:] == ends[:-1])        # contiguous, no overlap
    assert np.all(np.diff(centres) > 0)           # low to high


def test_bands_work_at_44100_too():
    starts, ends, _ = band_bins(44100, 2048, 64)
    assert np.all(ends > starts)


@pytest.mark.parametrize("freq", [80, 250, 1000, 4000, 12000])
def test_a_pure_tone_lights_the_right_bar(freq):
    a = Analyzer(SR, 16)
    levels = a.process(tone(freq))
    loudest = int(np.argmax(levels))
    lo = a.starts[loudest] * SR / 2048
    hi = a.ends[loudest] * SR / 2048
    # the tone falls in (or right beside) the loudest bar
    assert lo * 0.8 <= freq <= hi * 1.25, (freq, lo, hi)


def test_silence_gives_flat_bars():
    a = Analyzer(SR, 16)
    assert np.all(a.process(np.zeros(2048)) == 0)


def test_fade_out_whisper_is_not_amplified():
    """Automatic gain must not turn near-silence into full-height bars."""
    a = Analyzer(SR, 16)
    for _ in range(400):                          # 10 s of near-silence at 40 fps
        levels = a.process(tone(1000, amp=1e-5), dt=1 / 40)
    assert levels.max() < 0.2


def test_quiet_song_still_moves_after_gain_settles():
    a = Analyzer(SR, 16)
    for _ in range(400):
        levels = a.process(tone(1000, amp=0.05), dt=1 / 40)
    assert levels.max() > 0.9


def test_sensitivity_makes_bars_taller():
    x = DemoSource().read(2048, now=10.0)
    low = Analyzer(SR, 16).process(x, sensitivity=10)
    high = Analyzer(SR, 16).process(x, sensitivity=90)
    assert high.sum() > low.sum()


def test_smoother_rises_fast_falls_slowly_and_peaks_hold():
    s = BarSmoother(1)
    first, _ = s.update([1.0], 1 / 40)
    top = float(first[0])
    assert top >= 0.7                             # most of the way up in one frame
    levels, peaks = s.update([0.0], 1 / 40)
    assert 0.3 < levels[0] < top                  # falls, but not instantly
    assert peaks[0] == pytest.approx(top)         # cap stays at the top


def test_sound_detector_goes_quiet_after_hold():
    d = SoundDetector(hold_s=3.0)
    assert d.update(tone(440), now=100.0)
    assert d.update(np.zeros(2048), now=102.0)    # still within hold
    assert not d.update(np.zeros(2048), now=103.5)


@pytest.mark.parametrize("w,h", [(64, 32), (64, 64), (128, 64)])
def test_render_is_panel_sized_and_bars_fit(w, h):
    n = auto_bars(w)
    bar_w, gap, left = bar_layout(w, n)
    assert left >= 0 and left + n * (bar_w + gap) - gap <= w
    levels = np.linspace(0, 1, n)
    img = render(levels, levels, w, h)
    assert img.size == (w, h)
    px = np.asarray(img)
    # the tallest bar reaches the top row; the silent first bar only shows its floor
    x_last = left + (n - 1) * (bar_w + gap)
    assert px[0, x_last].any()
    assert not px[: h - 1, left].any()


@pytest.mark.parametrize("theme", THEMES)
def test_every_theme_draws(theme):
    img = render(np.full(16, 0.5), np.full(16, 0.8), 64, 32, theme=theme)
    assert np.asarray(img).any()


def test_album_palette_rejects_black_and_white_covers():
    from PIL import Image
    grey = Image.new("RGB", (64, 64), (128, 128, 128))
    assert album_palette(grey, 16) is None
    red = Image.new("RGB", (64, 64), (200, 30, 30))
    assert album_palette(red, 16).shape == (16, 3)


def test_airplay_reader_keeps_bytes_split_between_reads():
    # A pipe read can stop mid-frame. Dropping the leftover bytes used to
    # shift every later sample, turning music into hiss that filled the bars.
    from audio_source import to_mono
    rng = np.random.default_rng(3)
    stereo = (np.sin(np.arange(4800) * 0.05)[:, None] * [12000, 8000]).astype("<i2")
    raw = stereo.tobytes()
    out, rest, i = [], b"", 0
    while i < len(raw):
        step = int(rng.integers(1, 700))           # odd sizes, like a real pipe
        mono, rest = to_mono(rest + raw[i:i + step])
        out.append(mono)
        i += step
    got = np.concatenate(out)
    want = stereo.mean(axis=1) / 32768.0
    assert len(got) == len(want)
    assert np.allclose(got, want, atol=1e-6)
