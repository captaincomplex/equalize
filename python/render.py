"""
render.py -- draw bar heights as a picture the size of the LED panel.

Pure numpy + Pillow, no hardware, so it can be tested anywhere and so the web
panel's preview is drawn by exactly the same code as the LEDs.
"""

import colorsys

import numpy as np
from PIL import Image

THEMES = ["classic", "rainbow", "ice", "sunset", "album"]

# Colour stops from the bottom of the panel (0.0) to the top (1.0).
_GRADIENTS = {
    "classic": [(0.0, (0, 200, 40)), (0.55, (170, 220, 0)), (0.78, (255, 170, 0)), (1.0, (255, 20, 0))],
    "ice":     [(0.0, (0, 30, 160)), (0.5, (0, 150, 255)), (0.85, (120, 230, 255)), (1.0, (255, 255, 255))],
    "sunset":  [(0.0, (90, 0, 140)), (0.45, (230, 30, 90)), (0.8, (255, 130, 0)), (1.0, (255, 230, 60))],
}
IDLE_FLOOR = 0.12        # the always-lit bottom row, as a fraction of full colour


def bar_layout(width, n_bars):
    """Return (bar_width, gap, left_margin) that fits n_bars across width.

    A one-pixel gap separates bars when there's room (bars 2px or wider);
    leftover pixels are split evenly between the two edges.
    """
    n_bars = max(1, min(n_bars, width))
    slot = width // n_bars
    gap = 1 if slot >= 3 else 0
    bar_w = slot - gap
    used = n_bars * slot - gap
    return bar_w, gap, (width - used) // 2


def auto_bars(width):
    """A good default bar count: 4-pixel slots (3 lit + 1 gap)."""
    return max(4, width // 4)


def _gradient(stops, height):
    ys = np.linspace(0.0, 1.0, height)
    pos = [s[0] for s in stops]
    return np.stack([np.interp(ys, pos, [s[1][c] for s in stops]) for c in range(3)], axis=1)


def album_palette(art, n_bars):
    """Pick one vivid colour per bar from the album cover, left to right.

    Returns None for a cover with too little colour (black-and-white sleeves)
    so the caller can fall back to a built-in theme.
    """
    if art is None:
        return None
    small = art.convert("RGB").resize((n_bars, 8), Image.Resampling.BOX)
    px = np.asarray(small, dtype=float) / 255.0
    cols = []
    sats = []
    for i in range(n_bars):
        # the most saturated of the 8 samples down this column of the cover
        best = max((colorsys.rgb_to_hsv(*px[j, i]) for j in range(8)), key=lambda h: h[1] * h[2])
        h, s, v = best
        sats.append(s)
        cols.append(colorsys.hsv_to_rgb(h, max(s, 0.75), 1.0))
    if np.median(sats) < 0.18:
        return None
    return np.array(cols) * 255.0


def colour_field(theme, n_bars, height, palette=None):
    """Colour for every (row, bar): array of shape (height, n_bars, 3), row 0 = bottom."""
    if theme == "album" and palette is not None and len(palette) == n_bars:
        ramp = np.linspace(0.35, 1.0, height)[:, None, None]
        return ramp * palette[None, :, :]
    if theme == "rainbow":
        hues = np.linspace(0.0, 0.83, n_bars)
        cols = np.array([colorsys.hsv_to_rgb(h, 1.0, 1.0) for h in hues]) * 255.0
        ramp = np.linspace(0.45, 1.0, height)[:, None, None]
        return ramp * cols[None, :, :]
    grad = _GRADIENTS.get(theme, _GRADIENTS["classic"])
    col = _gradient(grad, height)
    return np.repeat(col[:, None, :], n_bars, axis=1)


def render(levels, peaks, width, height, theme="classic", palette=None,
           show_peaks=True, field=None):
    """Draw one frame. levels/peaks are 0..1 per bar. Returns a PIL RGB image.

    Pass a precomputed `field` (from colour_field) to skip rebuilding the
    colours every frame.
    """
    n = len(levels)
    bar_w, gap, left = bar_layout(width, n)
    if field is None:
        field = colour_field(theme, n, height, palette)
    img = np.zeros((height, width, 3), dtype=np.uint8)

    for i in range(n):
        x0 = left + i * (bar_w + gap)
        x1 = x0 + bar_w
        h = int(round(float(levels[i]) * height))
        # bottom row always faintly lit, so "on but silent" isn't a dead panel
        img[height - 1, x0:x1] = (field[0, i] * IDLE_FLOOR).astype(np.uint8)
        if h > 0:
            column = field[:h, i][::-1]                      # top-down
            img[height - h:, x0:x1] = column[:, None, :].astype(np.uint8)
        if show_peaks:
            p = int(round(float(peaks[i]) * height))
            if p > h and p > 1:
                row = height - p
                img[row, x0:x1] = np.minimum(255, field[p - 1, i] * 0.6 + 100).astype(np.uint8)
    return Image.fromarray(img, "RGB")
