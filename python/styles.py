"""
styles.py -- the four ways Equalize can draw the music, one per logo.

    sunset  bars standing on a horizon, the sun's slits cut through them,
            a neon grid floor below (logo 1, the default)
    disc    the spectrum as a ring of rays around a small striped sun (logo 3)
    meter   a hi-fi LED meter: stacked segments, unlit ones faintly glowing,
            a lit segment marking each peak (logo 4)
    equals  bars rising from a centre line with their reflection below,
            like an "=" sign (logo 5)
    bars    the plain equaliser from render.py

Every style takes the same inputs -- a level and a peak (0..1) per bar and a
colour field from render.colour_field -- so the colour themes work with all of
them. Pure numpy + Pillow: testable anywhere, and the web preview is drawn by
the same code as the LEDs.
"""

import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from render import IDLE_FLOOR, bar_layout, render

STYLES = ["sunset", "disc", "meter", "equals", "bars"]
STYLE_LABELS = {"sunset": "Sunset", "disc": "Disc", "meter": "Meter",
                "equals": "Equals", "bars": "Plain bars"}
CYAN = np.array([45, 226, 245], dtype=float)
DEEP_BLUE = np.array([27, 58, 143], dtype=float)
SUN_STOPS = [(0.0, (169, 75, 255)), (0.35, (255, 95, 200)), (0.7, (255, 157, 122)), (1.0, (255, 246, 160))]


def _column(field, i, rows):
    """Bar i's colours resampled to `rows` pixels, bottom first."""
    src = field[:, i]
    idx = np.linspace(0, len(src) - 1, max(rows, 1)).round().astype(int)
    return src[idx]


def _peak_rgb(field, i, peak_colour):
    if peak_colour is not None:
        return np.array(peak_colour, dtype=np.uint8)
    return np.minimum(255, field[-1, i] * 0.6 + 100).astype(np.uint8)


# ---------------------------------------------------------------- sunset
@lru_cache(maxsize=8)
def _sunset_floor(width, height, horizon):
    """The static neon grid below the horizon (drawn once per panel size)."""
    img = Image.new("RGB", (width, height))
    d = ImageDraw.Draw(img)
    line = tuple(int(v * 0.55) for v in CYAN)
    dim = tuple(int(v * 0.2) for v in CYAN)
    depth = height - horizon - 1
    if depth >= 2:
        cx = (width - 1) / 2
        n_rays = 4 if width <= 64 else 6                         # each side of the centre
        for k in range(-n_rays, n_rays + 1):                     # rays from the vanishing point
            xb = cx + k * (width * 0.9) / n_rays
            d.line([(cx + (xb - cx) * 0.08, horizon), (xb, height - 1)], fill=dim)
        for k in (1, 2, 3):                                      # rows, closing up with distance
            y = horizon + round(depth * (k / 3) ** 1.7)
            if horizon < y < height:
                d.line([(0, y), (width - 1, y)], fill=dim)
    d.line([(0, horizon), (width - 1, horizon)], fill=line)      # the horizon itself
    return np.asarray(img)


def _slit_rows(horizon):
    """Rows cut out of the bars, like the stripes of a vaporwave sun:
    wider and closer together near the horizon."""
    rows = set()
    for frac, thick in ((0.10, 2 if horizon >= 40 else 1), (0.24, 1), (0.38, 1)):
        y = horizon - 1 - round(horizon * frac)
        for t in range(thick):
            rows.add(y + t)
    return rows


def draw_sunset(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    horizon = round(height * 0.8)                                # bars stand on this row
    img = _sunset_floor(width, height, horizon).copy()
    slits = _slit_rows(horizon)
    n = len(levels)
    bar_w, gap, left = bar_layout(width, n)
    for i in range(n):
        x0 = left + i * (bar_w + gap)
        x1 = x0 + bar_w
        col = _column(field, i, horizon)
        img[horizon - 1, x0:x1] = (col[0] * IDLE_FLOOR).astype(np.uint8)
        h = int(round(float(levels[i]) * horizon))
        for k in range(h):                                       # k = 0 is just above the horizon
            y = horizon - 1 - k
            if y not in slits:
                img[y, x0:x1] = col[k].astype(np.uint8)
        if show_peaks:
            p = int(round(float(peaks[i]) * horizon))
            if p > h and p > 1:
                img[horizon - p, x0:x1] = _peak_rgb(field, i, peak_colour)
    return Image.fromarray(img, "RGB")


# ---------------------------------------------------------------- disc
@lru_cache(maxsize=8)
def _disc_sun(width, height):
    """The small striped sun at the centre (drawn once per panel size)."""
    img = Image.new("RGB", (width, height))
    d = ImageDraw.Draw(img)
    cx, cy = (width - 1) / 2, (height - 1) / 2
    r = max(3, round(min(width, height) * 0.17))
    for y in range(int(cy - r), int(cy + r) + 1):
        t = 1 - (y - (cy - r)) / (2 * r)                        # 1 at the top, 0 at the bottom
        pos = [s[0] for s in SUN_STOPS]
        rgb = tuple(int(np.interp(t, pos, [s[1][c] for s in SUN_STOPS])) for c in range(3))
        half = math.sqrt(max(0.0, r * r - (y - cy) ** 2))
        d.line([(cx - half, y), (cx + half, y)], fill=rgb)
    for frac in (0.3, 0.62):                                     # slits in the lower half
        y = round(cy + r * frac)
        d.line([(cx - r, y), (cx + r, y)], fill=(0, 0, 0))
    return img, r


def draw_disc(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    sun, r_sun = _disc_sun(width, height)
    img = sun.copy()
    d = ImageDraw.Draw(img)
    cx, cy = (width - 1) / 2, (height - 1) / 2
    r0 = r_sun + 2
    reach = max(2.0, min(width, height) / 2 - r0 - 0.5)
    # Rays need room: at most one per ~2.5 px of the ring's circumference, so
    # neighbouring bars are averaged together on a small ring.
    per_side = max(6, min(len(levels), int(math.pi * r0 / 2.5)))
    groups = np.array_split(np.arange(len(levels)), per_side)
    levels = np.array([np.max(np.asarray(levels)[g]) for g in groups])
    peaks = np.array([np.max(np.asarray(peaks)[g]) for g in groups])
    field = np.stack([field[:, g[len(g) // 2]] for g in groups], axis=1)
    n = per_side
    # bass at the bottom, treble at the top, mirrored left and right
    for side in (1, -1):
        for i in range(n):
            a = math.pi / 2 - side * math.pi * (i + 0.5) / n     # screen angle, y down
            ca, sa = math.cos(a), math.sin(a)
            length = float(levels[i]) * reach
            # colour follows the ray's length, like a bar's top colour
            top = field[int(float(levels[i]) * (len(field) - 1)), i] * (0.6 + 0.4 * float(levels[i]))
            if length >= 0.5:
                d.line([(cx + r0 * ca, cy + r0 * sa),
                        (cx + (r0 + length) * ca, cy + (r0 + length) * sa)],
                       fill=tuple(int(v) for v in top))
            else:
                d.point((cx + r0 * ca, cy + r0 * sa), fill=tuple(int(v * IDLE_FLOOR * 2) for v in field[0, i]))
            if show_peaks and float(peaks[i]) * reach > length + 1:
                pr = r0 + float(peaks[i]) * reach
                d.point((cx + pr * ca, cy + pr * sa), fill=tuple(int(v) for v in _peak_rgb(field, i, peak_colour)))
    return img


# ---------------------------------------------------------------- meter
def draw_meter(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    seg_h = max(1, height // 16)                                 # 4 px on a 64-high panel
    pitch = seg_h + 1
    n_seg = height // pitch
    bottom = height - (height - n_seg * pitch) // 2              # centre the stack vertically
    img = np.zeros((height, width, 3), dtype=np.uint8)
    n = len(levels)
    bar_w, gap, left = bar_layout(width, n)
    for i in range(n):
        x0 = left + i * (bar_w + gap)
        x1 = x0 + bar_w
        col = _column(field, i, n_seg)
        lit = int(round(float(levels[i]) * n_seg))
        pk = int(round(float(peaks[i]) * n_seg)) - 1
        for s in range(n_seg):
            y1 = bottom - s * pitch
            y0 = y1 - seg_h
            if s < lit:
                c = col[s]
            elif show_peaks and s == pk and pk >= lit:
                c = _peak_rgb(field, i, peak_colour)
            else:
                c = col[s] * 0.10                                # unlit: a faint glow
            img[y0:y1, x0:x1] = np.asarray(c).astype(np.uint8)
    return Image.fromarray(img, "RGB")


# ---------------------------------------------------------------- equals
def draw_equals(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    gap = max(1, height // 32)                                   # the space in the "="
    top_h = round((height - gap) * 0.62)                         # room for the upper bars
    base = top_h                                                 # first row of the reflection
    reflect_h = height - top_h - gap
    img = np.zeros((height, width, 3), dtype=np.uint8)
    n = len(levels)
    bar_w, gap_x, left = bar_layout(width, n)
    fade = np.linspace(1.0, 0.0, max(reflect_h, 1))[:, None]
    reflection = (CYAN * fade + DEEP_BLUE * (1 - fade)) * np.linspace(1.0, 0.45, max(reflect_h, 1))[:, None]
    for i in range(n):
        x0 = left + i * (bar_w + gap_x)
        x1 = x0 + bar_w
        col = _column(field, i, top_h)
        img[top_h - 1, x0:x1] = (col[0] * IDLE_FLOOR).astype(np.uint8)
        h = int(round(float(levels[i]) * top_h))
        if h > 0:
            img[top_h - h:top_h, x0:x1] = col[:h][::-1][:, None, :].astype(np.uint8)
        rh = int(round(float(levels[i]) * reflect_h * 0.85))
        if rh > 0:
            img[base + gap:base + gap + rh, x0:x1] = reflection[:rh][:, None, :].astype(np.uint8)
        if show_peaks:
            p = int(round(float(peaks[i]) * top_h))
            if p > h and p > 1:
                img[top_h - p, x0:x1] = _peak_rgb(field, i, peak_colour)
    return Image.fromarray(img, "RGB")


def draw(style, levels, peaks, width, height, field, peak_colour=None, show_peaks=True):
    """Draw one frame in the named style. Unknown names fall back to sunset."""
    if style == "bars":
        return render(levels, peaks, width, height, show_peaks=show_peaks,
                      field=field, peak_colour=peak_colour)
    fn = {"sunset": draw_sunset, "disc": draw_disc, "meter": draw_meter,
          "equals": draw_equals}.get(style, draw_sunset)
    return fn(levels, peaks, width, height, field, peak_colour, show_peaks)


# A pleasing, fixed set of levels for previews (web panel style picker, docs).
def sample_levels(n):
    x = np.linspace(0, 1, n)
    levels = 0.35 + 0.45 * np.exp(-((x - 0.18) / 0.16) ** 2) + 0.25 * np.sin(x * 11) ** 2 * (1 - x)
    levels = np.clip(levels, 0.05, 0.95)
    peaks = np.clip(levels + 0.08 + 0.06 * np.cos(x * 7), 0, 1)
    return levels, peaks
