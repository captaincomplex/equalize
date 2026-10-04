"""
render.py -- draw bar heights as a picture the size of the LED panel.

Pure numpy + Pillow, no hardware, so it can be tested anywhere and so the web
panel's preview is drawn by exactly the same code as the LEDs.
"""

import colorsys

import numpy as np
from PIL import Image

THEMES = ["vapor", "classic", "rainbow", "ice", "sunset",
          "fire", "ocean", "forest", "aurora", "amber", "mono", "pastel", "thermal",
          "album"]

# Colour stops from the bottom of the panel (0.0) to the top (1.0).
_GRADIENTS = {
    # the logo's sun: purple at the horizon, through pink and peach, to pale yellow
    "vapor":   [(0.0, (169, 75, 255)), (0.35, (255, 95, 200)), (0.7, (255, 157, 122)), (1.0, (255, 246, 160))],
    "classic": [(0.0, (0, 200, 40)), (0.55, (170, 220, 0)), (0.78, (255, 170, 0)), (1.0, (255, 20, 0))],
    "ice":     [(0.0, (0, 30, 160)), (0.5, (0, 150, 255)), (0.85, (120, 230, 255)), (1.0, (255, 255, 255))],
    "sunset":  [(0.0, (90, 0, 140)), (0.45, (230, 30, 90)), (0.8, (255, 130, 0)), (1.0, (255, 230, 60))],
    # embers at the bottom, white-hot at the top
    "fire":    [(0.0, (120, 0, 0)), (0.4, (230, 40, 0)), (0.75, (255, 150, 0)), (1.0, (255, 245, 200))],
    # deep water up to surf
    "ocean":   [(0.0, (0, 30, 90)), (0.45, (0, 110, 160)), (0.8, (0, 200, 190)), (1.0, (200, 255, 240))],
    # moss to new leaves to sunlight
    "forest":  [(0.0, (0, 70, 20)), (0.5, (30, 160, 40)), (0.85, (160, 230, 40)), (1.0, (255, 240, 120))],
    # the northern lights: green low down, violet at the top
    "aurora":  [(0.0, (0, 140, 70)), (0.45, (0, 220, 160)), (0.75, (60, 120, 255)), (1.0, (190, 80, 255))],
    # one colour, like the glowing display of an old hi-fi
    "amber":   [(0.0, (120, 45, 0)), (0.6, (255, 140, 0)), (1.0, (255, 200, 80))],
    # warm white, brightening with height: calm, goes with any room
    "mono":    [(0.0, (70, 60, 50)), (0.6, (200, 185, 165)), (1.0, (255, 250, 240))],
    # soft sweet-shop colours
    "pastel":  [(0.0, (120, 170, 255)), (0.35, (190, 140, 255)), (0.7, (255, 150, 200)), (1.0, (255, 230, 170))],
    # a heat camera: cold blue up through red to white-hot
    "thermal": [(0.0, (20, 0, 120)), (0.3, (150, 0, 160)), (0.55, (240, 30, 40)),
                (0.8, (255, 170, 0)), (1.0, (255, 255, 230))],
}
# Peak caps are normally a paler version of the bar's top colour; some themes
# use a contrasting accent instead (vapor: the logo's neon-grid cyan).
_PEAK_COLOURS = {"vapor": (45, 226, 245)}
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


def theme_css(theme):
    """A CSS gradient showing a theme, for the web panel's colour picker."""
    if theme == "rainbow":
        return "linear-gradient(90deg, %s)" % ", ".join(
            "hsl(%d 100%% 55%%)" % h for h in (0, 60, 120, 180, 240, 300))
    if theme == "album":
        return "linear-gradient(135deg, #ff5fc8, #ffb35c 35%, #2de2f5 70%, #a94bff)"
    stops = _GRADIENTS.get(theme, _GRADIENTS["classic"])
    return "linear-gradient(0deg, %s)" % ", ".join(
        "rgb(%d %d %d) %d%%" % (c[0], c[1], c[2], p * 100) for p, c in stops)


def render(levels, peaks, width, height, theme="classic", palette=None,
           show_peaks=True, field=None, peak_colour=None):
    """Draw one frame. levels/peaks are 0..1 per bar. Returns a PIL RGB image.

    Pass a precomputed `field` (from colour_field) to skip rebuilding the
    colours every frame. peak_colour overrides the theme's cap colour.
    """
    if peak_colour is None:
        peak_colour = _PEAK_COLOURS.get(theme)
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
                img[row, x0:x1] = (peak_colour if peak_colour is not None else
                                   np.minimum(255, field[p - 1, i] * 0.6 + 100).astype(np.uint8))
    return Image.fromarray(img, "RGB")


def peak_colour_for(theme):
    """The fixed cap colour for a theme, or None for "paler top colour"."""
    return _PEAK_COLOURS.get(theme)
