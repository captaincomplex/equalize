"""
styles.py -- the four ways Equalize can draw the music, one per logo.

    sunset  bars standing on a horizon, the sun's slits cut through them,
            a neon grid floor below (logo 1, the default)
    disc    the spectrum as a ring of rays around a small striped sun (logo 3)
    meter   a hi-fi LED meter: stacked segments, unlit ones faintly glowing,
            a lit segment marking each peak (logo 4)
    equals  bars rising from a centre line with their reflection below,
            like an "=" sign (logo 5)
    mirror  bars growing up and down from the middle of the panel at once
    wave    one smooth line through the tops of the bars, softly filled below
    waterfall  the last few seconds of music scrolling down the panel, newest
            at the top, brighter where it's louder -- you can see the beat
    vu      a needle meter like an old hi-fi; on a wide panel, two of them,
            bass on the left and treble on the right
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

STYLES = ["sunset", "disc", "meter", "equals", "mirror", "wave", "waterfall", "vu", "bars"]
STYLE_LABELS = {"sunset": "Sunset", "disc": "Disc", "meter": "Meter",
                "equals": "Equals", "mirror": "Mirror", "wave": "Wave",
                "waterfall": "Waterfall", "vu": "Needle", "bars": "Plain bars"}
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
    dim = np.linspace(1.0, 0.45, max(reflect_h, 1))[:, None]
    # Vapor's reflection is the logo's cyan; other themes reflect their own
    # colours, like water would.
    accent = peak_colour is not None
    reflection = (CYAN * fade + DEEP_BLUE * (1 - fade)) * dim
    for i in range(n):
        if not accent:
            reflection = _column(field, i, reflect_h) * dim * 0.7
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


# ---------------------------------------------------------------- mirror
def draw_mirror(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    """Bars grow up and down from the middle row at the same time. The colour
    runs from the theme's bottom colour at the centre to its top colour at the
    ends, so loud bars reach the bright end both ways."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    half = height // 2                                           # rows each side of the centre
    top_c = height // 2 - 1                                      # centre row of the upper half
    n = len(levels)
    bar_w, gap, left = bar_layout(width, n)
    for i in range(n):
        x0 = left + i * (bar_w + gap)
        x1 = x0 + bar_w
        col = _column(field, i, half)
        img[top_c, x0:x1] = (col[0] * IDLE_FLOOR).astype(np.uint8)
        img[top_c + 1, x0:x1] = (col[0] * IDLE_FLOOR).astype(np.uint8)
        h = int(round(float(levels[i]) * half))
        if h > 0:
            img[top_c - h + 1:top_c + 1, x0:x1] = col[:h][::-1][:, None, :].astype(np.uint8)
            img[top_c + 1:top_c + 1 + h, x0:x1] = col[:h][:, None, :].astype(np.uint8)
        if show_peaks:
            p = int(round(float(peaks[i]) * half))
            if p > h and p > 1:
                pc = _peak_rgb(field, i, peak_colour)
                img[top_c - p + 1, x0:x1] = pc
                img[min(height - 1, top_c + p), x0:x1] = pc
    return Image.fromarray(img, "RGB")


# ---------------------------------------------------------------- wave
def _smooth_curve(values, width):
    """Bar values spread across every column, then softened so the line flows
    instead of stepping from bar to bar."""
    n = len(values)
    xs = (np.arange(n) + 0.5) / n * width - 0.5
    curve = np.interp(np.arange(width), xs, np.asarray(values, dtype=float))
    k = max(1, width // max(n, 1))                               # about one bar wide
    kernel = np.exp(-0.5 * (np.arange(-2 * k, 2 * k + 1) / max(k * 0.6, 0.5)) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(curve, 2 * k, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def draw_wave(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    """One bright line through the tops of the bars, the area under it filled
    with the same colours, dimmed -- a hill range that moves with the music."""
    n = len(levels)
    curve = np.clip(_smooth_curve(levels, width), 0, 1)
    ys = np.round(curve * (height - 1)).astype(int)              # rows above the bottom
    bar_of = np.minimum(n - 1, np.arange(width) * n // width)    # which bar each column belongs to
    # colours for every (row above the bottom, column), then flipped to screen rows
    idx = np.round(np.arange(height) / max(height - 1, 1) * (len(field) - 1)).astype(int)
    cols = field[idx][:, bar_of]                                 # (height, width, 3), row 0 = bottom
    up = np.arange(height)[:, None]
    # the line: from each column's height to halfway to its neighbour's, so
    # steep slopes stay joined
    nb_lo = np.minimum(ys, np.r_[ys[0], ys[:-1]])
    nb_hi = np.maximum(ys, np.r_[ys[0], ys[:-1]])
    lo = np.where(nb_hi - nb_lo > 1, (nb_lo + nb_hi) // 2, nb_lo)
    lo = np.minimum(lo, ys)
    hi = nb_hi
    line = (up >= lo[None, :]) & (up <= hi[None, :])
    fill = up <= ys[None, :]
    img = np.where(fill[..., None], cols * 0.32, 0.0)
    img = np.where(line[..., None], np.minimum(255, cols + 30), img)
    if show_peaks:
        pys = np.round(np.clip(_smooth_curve(peaks, width), 0, 1) * (height - 1)).astype(int)
        for x in range(0, width, 3):                             # a dotted line where it was
            if pys[x] > ys[x] + 2:
                img[pys[x], x] = _peak_rgb(field, bar_of[x], peak_colour) * 0.6
    return Image.fromarray(img[::-1].astype(np.uint8), "RGB")


# ---------------------------------------------------------------- waterfall
# The waterfall remembers the last few seconds. One history per panel size and
# bar count; a new row is added every WATERFALL_EVERY frames (about 13 rows a
# second at 40 frames a second), carrying the loudest moment since the last.
WATERFALL_EVERY = 3
_falls = {}


class _Fall:
    def __init__(self, rows, n):
        self.rows = np.zeros((rows, n))
        self.pending = np.zeros(n)
        self.count = 0


def _still_history(levels, rows):
    """A made-up few seconds for the style picker's still picture."""
    t = np.arange(rows)[:, None]
    beat = 0.55 + 0.45 * (np.cos(t * 2 * math.pi / 7) > 0.2)
    wobble = 0.85 + 0.15 * np.sin(t * 0.9 + np.arange(len(levels))[None, :] * 0.7)
    return np.clip(np.asarray(levels)[None, :] * beat * wobble, 0, 1)


def draw_waterfall(levels, peaks, width, height, field, peak_colour, show_peaks=True, still=False):
    n = len(levels)
    if still:
        hist = _still_history(levels, height)
    else:
        key = (width, height, n)
        fall = _falls.get(key)
        if fall is None:
            _falls.clear()                                       # one panel at a time
            fall = _falls[key] = _Fall(height, n)
        fall.pending = np.maximum(fall.pending, levels)
        fall.count += 1
        if fall.count >= WATERFALL_EVERY:
            fall.rows = np.roll(fall.rows, 1, axis=0)
            fall.rows[0] = fall.pending
            fall.pending = np.zeros(n)
            fall.count = 0
        hist = fall.rows.copy()
        hist[0] = np.maximum(hist[0], levels)                    # the top row is live
    bar_w, gap, left = bar_layout(width, n)
    img = np.zeros((height, width, 3), dtype=np.uint8)
    top = len(field) - 1
    for i in range(n):
        x0 = left + i * (bar_w + gap)
        x1 = x0 + bar_w
        v = hist[:, i]
        # louder = further up the theme's colours, and brighter
        cols = field[np.round(v * top).astype(int), i] * (0.08 + 0.92 * v[:, None] ** 1.3)
        img[:, x0:x1] = cols[:, None, :].astype(np.uint8)
    return Image.fromarray(img, "RGB")


# ---------------------------------------------------------------- vu (needle)
VU_SWING = math.radians(48)                                      # each side of upright


def _vu_level(levels):
    """How loud, 0..1: the average of the louder half of the bars, so a single
    booming bass note doesn't pin the needle."""
    v = np.sort(np.asarray(levels, dtype=float))[len(levels) // 2:]
    return float(np.clip(v.mean() * 1.15, 0, 1)) if len(v) else 0.0


def _vu_meter(d, box, level, peak, field, peak_colour, show_peaks):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx = x0 + (w - 1) / 2
    # As long as the width allows: the arc's ends sit sin(swing) * r either side.
    r = min((w / 2 - 1) / math.sin(VU_SWING), h * 0.92)          # needle length
    # centre the dial (arc top to hub) top to bottom
    span = r + max(1, round(r * 0.06))
    cy = y0 + max(0, (h - 1 - span) // 2) + r
    n_rows = len(field)

    def at(frac, radius):
        a = -VU_SWING + 2 * VU_SWING * frac                      # 0 = hard left
        return cx + radius * math.sin(a), cy - radius * math.cos(a)

    # The dial face, faintly lit like the window of an old hi-fi meter.
    face = field[int(0.5 * (n_rows - 1)), 0] * 0.07
    d.pieslice([cx - r, cy - r, cx + r, cy + r],
               math.degrees(-VU_SWING) - 90, math.degrees(VU_SWING) - 90,
               fill=tuple(int(v) for v in face))
    # The scale: an arc of the theme's colours, low to high from left to
    # right; ticks every tenth, the last fifth (the "red zone") at full colour.
    steps = max(24, int(r * 2.5))
    for k in range(steps + 1):
        f = k / steps
        c = field[int(f * (n_rows - 1)), 0] * (1.0 if f >= 0.8 else 0.45)
        d.point(at(f, r), fill=tuple(int(v) for v in c))
    for k in range(11):
        f = k / 10
        c = field[int(f * (n_rows - 1)), 0] * (1.0 if f >= 0.8 else 0.75)
        d.line([at(f, r - max(1, r * (0.14 if k % 5 == 0 else 0.08))), at(f, r)],
               fill=tuple(int(v) for v in c))
    if show_peaks and peak > level + 0.02:
        pc = _peak_rgb(field, 0, peak_colour)
        d.line([at(peak, r - max(1, r * 0.2)), at(peak, r)], fill=tuple(int(v) for v in pc))
    # the needle: pale, tinted with the colour it points at; two LEDs wide on
    # a big dial so it reads from across the room
    tip = field[int(level * (n_rows - 1)), 0]
    needle = tuple(int(min(255, v * 0.35 + 165)) for v in tip)
    d.line([at(level, r * 0.08), at(level, r - 1)], fill=needle, width=2 if r >= 20 else 1)
    hub = max(1, round(r * 0.06))
    d.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=needle)


def draw_vu(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    img = Image.new("RGB", (width, height))
    d = ImageDraw.Draw(img)
    n = len(levels)
    # field[:, 0] is the first bar's colours; for a per-bar theme (rainbow,
    # album) use the middle bar so the needle isn't always red
    f = field[:, [n // 2]] if field.shape[1] > 1 else field
    if width >= 2 * height:                                      # wide: bass | treble
        half = width // 2
        lv, pk = np.asarray(levels), np.asarray(peaks)
        _vu_meter(d, (0, 0, half, height), _vu_level(lv[:n // 2]), _vu_level(pk[:n // 2]),
                  field[:, [n // 4]], peak_colour, show_peaks)
        _vu_meter(d, (half, 0, width, height), _vu_level(lv[n // 2:]), _vu_level(pk[n // 2:]),
                  field[:, [3 * n // 4]], peak_colour, show_peaks)
    else:
        _vu_meter(d, (0, 0, width, height), _vu_level(levels), _vu_level(peaks),
                  f, peak_colour, show_peaks)
    return img


def draw(style, levels, peaks, width, height, field, peak_colour=None, show_peaks=True, still=False):
    """Draw one frame in the named style. Unknown names fall back to sunset.
    still=True is for a single picture (the web panel's style picker), where
    the waterfall has no real history to show and makes one up."""
    if style == "bars":
        return render(levels, peaks, width, height, show_peaks=show_peaks,
                      field=field, peak_colour=peak_colour)
    if style == "waterfall":
        return draw_waterfall(levels, peaks, width, height, field, peak_colour, show_peaks, still)
    fn = {"sunset": draw_sunset, "disc": draw_disc, "meter": draw_meter,
          "equals": draw_equals, "mirror": draw_mirror, "wave": draw_wave,
          "vu": draw_vu}.get(style, draw_sunset)
    return fn(levels, peaks, width, height, field, peak_colour, show_peaks)


# A pleasing, fixed set of levels for previews (web panel style picker, docs).
def sample_levels(n):
    x = np.linspace(0, 1, n)
    levels = 0.35 + 0.45 * np.exp(-((x - 0.18) / 0.16) ** 2) + 0.25 * np.sin(x * 11) ** 2 * (1 - x)
    levels = np.clip(levels, 0.05, 0.95)
    peaks = np.clip(levels + 0.08 + 0.06 * np.cos(x * 7), 0, 1)
    return levels, peaks
