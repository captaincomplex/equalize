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
    analyser  Winamp's spectrum analyser: thin bars, colours fixed by height,
            grey peak dots, on a faint grid
    scope   Winamp's oscilloscope: the sound wave itself, held steady
    trails  every picture zooms out and fades behind the next, like
            MilkDrop or Windows Media Player
    plasma  flowing colour pushed around by the bass, like Media Player's
            "Ambience"
    ledring rings of LED dots around the middle, lit outward further where
            the music is louder (the LED ring logo; the default)
    ring    rays around an empty circle, longer where louder (the Ring logo)
    dots    big round "LEDs" in columns, the unlit ones faintly showing (the
            LED grid logo)
    dance   Dance Dance Revolution: four lanes (or eight, with diagonals),
            lowest notes on the left, send rounded arrows scrolling up to a
            row of targets on each beat
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

STYLES = ["ledring", "ring", "dots", "sunset", "disc", "meter", "equals", "mirror", "wave",
          "waterfall", "vu", "analyser", "scope", "trails", "plasma", "dance", "bars"]
STYLE_LABELS = {"dance": "Dance", "ledring": "LED ring", "ring": "Ring", "dots": "LED grid", "sunset": "Sunset", "disc": "Disc", "meter": "Meter",
                "equals": "Equals", "mirror": "Mirror", "wave": "Wave",
                "waterfall": "Waterfall", "vu": "Needle", "analyser": "Analyser",
                "scope": "Scope", "trails": "Trails", "plasma": "Plasma",
                "bars": "Plain bars"}
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


# ---------------------------------------------------------------- analyser
@lru_cache(maxsize=8)
def _analyser_grid(width, height):
    """The faint dot grid behind Winamp's analyser."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[1::2, ::2] = 14
    return img


def draw_analyser(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    """Winamp's analyser: thin bars with a one-pixel gap, each row a fixed
    colour (so the top of a loud bar is always the hot colour), and a grey
    dot hanging at each peak."""
    img = _analyser_grid(width, height).copy()
    n = len(levels)
    bar_w, gap, left = bar_layout(width, n)
    rows = field[np.linspace(0, len(field) - 1, height).round().astype(int)]   # bottom first
    for i in range(n):
        x0 = left + i * (bar_w + gap)
        x1 = x0 + bar_w
        h = int(round(float(levels[i]) * height))
        if h > 0:
            img[height - h:, x0:x1] = rows[:h, i][::-1][:, None, :].astype(np.uint8)
        if show_peaks:
            p = int(round(float(peaks[i]) * height))
            if p > h and p > 0:
                img[height - p, x0:x1] = peak_colour if peak_colour is not None else (150, 150, 150)
    return Image.fromarray(img, "RGB")


# ---------------------------------------------------------------- scope
_scope_gain = {"peak": 0.05}


def _made_up_wave(levels, n):
    """A wave built from the bar levels, for when there's no real sound to
    hand (the style picker's still picture)."""
    t = np.linspace(0, 2 * math.pi, n)
    w = np.zeros(n)
    for i, lv in enumerate(np.asarray(levels, dtype=float)):
        w += lv * np.sin(t * (1 + i * 1.7) + i) / (1 + i * 0.4)
    return w


def draw_scope(levels, peaks, width, height, field, peak_colour, show_peaks=True, wave=None):
    """The sound wave itself, as on Winamp's oscilloscope. It starts each
    picture where the wave crosses zero going up (as a real scope's trigger
    does), so a steady note stands still instead of jittering."""
    if wave is None or len(wave) < width * 2:
        w = _made_up_wave(levels, width)
    else:
        x = np.asarray(wave, dtype=float)
        x = x - x.mean()
        span = min(len(x) // 2, width * 6)                       # about 6 ms at 48 kHz on a 64-wide panel
        start = 0
        search = x[: len(x) - span]
        ups = np.nonzero((search[:-1] < 0) & (search[1:] >= 0))[0]
        if len(ups):
            start = int(ups[-1])
        w = x[start:start + span]
        w = w[np.linspace(0, len(w) - 1, width).round().astype(int)]
    # slow automatic gain, so quiet music still fills the screen
    peak = float(np.max(np.abs(w))) if len(w) else 0.0
    _scope_gain["peak"] = max(peak, _scope_gain["peak"] * 0.97, 0.02)
    w = np.clip(w / _scope_gain["peak"], -1, 1)

    img = np.zeros((height, width, 3), dtype=np.uint8)
    mid = (height - 1) / 2
    img[int(round(mid)), ::2] = 18                               # a dotted centre line
    ys = np.round(mid - w * mid * 0.92).astype(int)
    n = field.shape[1]
    for x in range(width):
        i = min(n - 1, x * n // width)
        a, b = (ys[x], ys[x]) if x == 0 else sorted((ys[x - 1], ys[x]))
        loud = abs(float(w[x]))
        c = field[int((0.45 + 0.55 * loud) * (len(field) - 1)), i]     # the bright half of the colours
        c = np.minimum(255, c * 1.1 + 30).astype(np.uint8)
        img[a:b + 1, x] = c
        if height >= 48:                                         # two LEDs thick on a tall panel
            img[min(height - 1, b + 1), x] = c
    return Image.fromarray(img, "RGB")


# ---------------------------------------------------------------- trails
_trails = {}


def _trail_core(levels, peaks, width, height, field, peak_colour):
    """This moment's mirrored bars, drawn at 60% size in the middle."""
    cw, ch = max(4, int(width * 0.6)), max(4, int(height * 0.6))
    core = draw_mirror(levels, peaks, cw, ch, field, peak_colour, False)
    out = np.zeros((height, width, 3), dtype=float)
    ox, oy = (width - cw) // 2, (height - ch) // 2
    out[oy:oy + ch, ox:ox + cw] = np.asarray(core, dtype=float)
    return out


def _grow(img, s, fade):
    """Enlarge a picture about its middle by s, cropped back to size, faded."""
    h, w = img.shape[:2]
    big = Image.fromarray(img.astype(np.uint8)).resize((int(w * s), int(h * s)), Image.BILINEAR)
    ox, oy = (big.width - w) // 2, (big.height - h) // 2
    return np.asarray(big.crop((ox, oy, ox + w, oy + h)), dtype=float) * fade


def draw_trails(levels, peaks, width, height, field, peak_colour, show_peaks=True, still=False):
    """Every picture grows a little and fades behind the next, so the music
    flies out of the middle of the panel towards you, like MilkDrop or
    Windows Media Player."""
    now = _trail_core(levels, peaks, width, height, field, peak_colour)
    if still:                                                    # a made-up history for the still
        acc = now.copy()
        for k in range(1, 9):
            acc = np.maximum(acc, _grow(now, 1 + 0.08 * k, 0.82 ** k))
        return Image.fromarray(acc.astype(np.uint8), "RGB")
    key = (width, height)
    prev = _trails.get(key)
    if prev is None:
        _trails.clear()
        prev = np.zeros_like(now)
    out = np.maximum(_grow(prev, 1.06, 0.86), now)
    _trails[key] = out
    return Image.fromarray(out.astype(np.uint8), "RGB")


# ---------------------------------------------------------------- plasma
@lru_cache(maxsize=8)
def _plasma_grid(width, height):
    y, x = np.mgrid[0:height, 0:width].astype(float)
    cx, cy = (width - 1) / 2, (height - 1) / 2
    r = np.hypot(x - cx, y - cy) / max(width, height)
    return x / max(width, height), y / max(width, height), r


def draw_plasma(levels, peaks, width, height, field, peak_colour, show_peaks=True, t=None):
    """Slow flowing colour; the bass pushes ripples out from the middle and
    the overall loudness sets how bright it is."""
    x, y, r = _plasma_grid(width, height)
    if t is None:
        import time
        t = time.monotonic()
    lv = np.asarray(levels, dtype=float)
    q = max(1, len(lv) // 4)
    bass, treble = float(lv[:q].mean()), float(lv[-q:].mean())
    loud = float(np.sort(lv)[len(lv) // 2:].mean()) if len(lv) else 0.0
    v = (np.sin(x * 7 + t * 0.7)
         + np.sin((y * 6 - t * 0.5) + np.sin(x * 3 + t * 0.3))
         + np.sin(r * (14 + 10 * bass) - t * (2 + 4 * bass)) * (0.6 + bass)
         + np.sin((x + y) * (5 + 8 * treble) + t))
    v = (v - v.min()) / max(1e-6, v.max() - v.min())             # 0..1
    v = v ** 1.6                                                 # deeper lows, so the bright folds stand out
    # colour from the theme's ramp, using the middle bar for per-bar themes
    col = field[:, field.shape[1] // 2]
    idx = (v * (len(col) - 1)).astype(int)
    img = col[idx] * (0.08 + 0.92 * v)[..., None] * (0.3 + 0.7 * min(1.0, loud * 1.2))
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------- logo styles
def _around(levels, peaks, n):
    """Bars shared out round a circle: n spokes, bass at the bottom, treble at
    the top, mirrored left and right (as Disc does), loudest of each group."""
    lv, pk = np.asarray(levels, dtype=float), np.asarray(peaks, dtype=float)
    half = max(1, min(n // 2, len(lv)))                           # never more spokes than bars
    groups = np.array_split(np.arange(len(lv)), half)
    l = np.array([lv[g].max() for g in groups])
    p = np.array([pk[g].max() for g in groups])
    idx = [g[len(g) // 2] for g in groups]
    spokes = []
    for side in (1, -1):
        for i in range(half):
            a = math.pi / 2 - side * math.pi * (i + 0.5) / half       # screen angle, y down
            spokes.append((a, l[i], p[i], idx[i]))
    return spokes


def _led(img, x, y, size, colour):
    """One "LED": a size x size block (2x2 on a big panel). On a real panel
    the gap round it makes it read as a round dot."""
    x0, y0 = int(round(x - (size - 1) / 2)), int(round(y - (size - 1) / 2))
    h, w = img.shape[:2]
    if 0 <= x0 and x0 + size <= w and 0 <= y0 and y0 + size <= h:
        img[y0:y0 + size, x0:x0 + size] = colour


def draw_ledring(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    """Rings of LED dots round the middle, the dots growing as they go out
    (1, then 2, then 3 LEDs across on a 64-high panel), like the LED ring
    logo. The inner ring is always faintly lit; each spoke lights outward,
    further where the music is louder. Unlit dots glow very faintly."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cx, cy = (width - 1) / 2, (height - 1) / 2
    size = min(width, height)
    big = 3 if size >= 96 else 2 if size >= 48 else 1     # the outermost dot, in LEDs
    rings = max(3, min(6, int(size / 12)))
    sizes = [1 + round((big - 1) * j / max(1, rings - 1)) for j in range(rings)]
    r_in = size * 0.15
    # space the rings so each dot has a gap of at least one LED to the next
    radii = [r_in]
    for j in range(1, rings):
        radii.append(radii[-1] + (sizes[j - 1] + sizes[j]) / 2 + 1.6)
    scale = (size / 2 - sizes[-1] / 2 - 0.5 - r_in) / max(1e-6, radii[-1] - r_in)
    radii = [r_in + (r - r_in) * min(1.0, max(scale, 0.6)) for r in radii]
    n = max(10, min(36, int(2 * math.pi * r_in / 2.2)))
    rows = len(field) - 1
    for a, lv, pk, i in _around(levels, peaks, n):
        lit = int(round(lv * rings))
        top = int(round(pk * rings)) - 1
        for j in range(rings):
            col = field[int((0.45 + 0.55 * j / max(1, rings - 1)) * rows), i]   # the bright part of the colours
            if j < lit:
                c = col
            elif show_peaks and j == top and j > 0:
                c = _peak_rgb(field, i, peak_colour)
            elif j == 0:
                c = col * 0.45                                   # the ring itself, always there
            else:
                c = col * 0.07
            r = radii[j]
            _led(img, cx + r * math.cos(a), cy + r * math.sin(a), sizes[j], np.asarray(c).astype(np.uint8))
    return Image.fromarray(img, "RGB")


def draw_ring(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    """Rays round an empty circle, longer where the music is louder and
    widening as they go out, like the Ring logo; the circle itself always
    faintly lit."""
    img = Image.new("RGB", (width, height))
    d = ImageDraw.Draw(img)
    cx, cy = (width - 1) / 2, (height - 1) / 2
    size = min(width, height)
    r0 = size * 0.2
    reach = size / 2 - r0 - 1.5
    rows = len(field) - 1
    mid = field.shape[1] // 2
    d.ellipse([cx - r0 + 2, cy - r0 + 2, cx + r0 - 2, cy + r0 - 2],
              outline=tuple(int(v) for v in field[rows // 2, mid] * 0.7), width=1)
    n = max(10, min(32, int(2 * math.pi * r0 / 3.4)))          # room between spokes
    w_end = 2.0 if size >= 48 else 1.0                         # a gentle taper: 1 LED at the circle, 2 at the tip
    for a, lv, pk, i in _around(levels, peaks, n):
        ca, sa = math.cos(a), math.sin(a)
        px, py = -sa, ca
        length = lv * reach
        c = tuple(int(v) for v in field[int(lv * rows), i])
        if length >= 0.5:
            r1 = r0 + length
            w1 = 1 + (w_end - 1) * (length / reach)
            pts = [(cx + r0 * ca, cy + r0 * sa),
                   (cx + r1 * ca + px * w1 / 2, cy + r1 * sa + py * w1 / 2),
                   (cx + r1 * ca - px * w1 / 2, cy + r1 * sa - py * w1 / 2)]
            d.polygon(pts, fill=c)
            d.line([(cx + r0 * ca, cy + r0 * sa), (cx + r1 * ca, cy + r1 * sa)], fill=c, width=1)
        if show_peaks and pk * reach > length + 1.5:
            pr = r0 + pk * reach
            d.point((cx + pr * ca, cy + pr * sa), fill=tuple(int(v) for v in _peak_rgb(field, i, peak_colour)))
    return img


def draw_dots(levels, peaks, width, height, field, peak_colour, show_peaks=True):
    """Big "LEDs" in columns (2x2 with a gap on a big panel), the unlit ones
    faintly showing, like the LED grid logo."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    n = len(levels)
    dot = 2 if min(width, height) >= 48 else 1
    pitch = dot + 1
    cols, rows_n = width // pitch, height // pitch
    left = (width - cols * pitch + 1) // 2
    top_edge = (height - rows_n * pitch + 1) // 2
    frows = len(field) - 1
    for c in range(cols):
        i = min(n - 1, c * n // cols)
        lit = int(round(float(levels[i]) * rows_n))
        top = int(round(float(peaks[i]) * rows_n)) - 1
        for r in range(rows_n):                                  # r = 0 is the bottom row
            col = field[int(r / max(1, rows_n - 1) * frows), i]
            if r < lit:
                fill = col
            elif show_peaks and r == top:
                fill = _peak_rgb(field, i, peak_colour)
            else:
                fill = col * 0.07
            x0 = left + c * pitch
            y0 = top_edge + (rows_n - 1 - r) * pitch
            img[y0:y0 + dot, x0:x0 + dot] = np.asarray(fill).astype(np.uint8)
    return Image.fromarray(img, "RGB")

# ---------------------------------------------------------------- dance
# Dance Dance Revolution: four lanes, left/down/up/right, for the bass, low
# mid, high mid and treble. Each time a lane's part of the music hits, an
# arrow appears at the bottom and scrolls up to that lane's target at the
# top, which flashes as it arrives. Like the waterfall, it keeps a little
# state per panel size: the arrows on screen and each lane's recent level.
# Lanes left to right, lowest notes first. Four: the classic left, down, up,
# right. Eight: the diagonals too, the left-pointing ones on the left and
# the right-pointing ones on the right, with down and up in the middle.
DANCE_LANES = {4: ("W", "S", "N", "E"),
               8: ("W", "NW", "SW", "S", "N", "SE", "NE", "E")}
_ANGLE = {"N": 0, "NE": -45, "E": -90, "SE": -135, "S": 180, "SW": 135, "W": 90, "NW": 45}
_dance = {}


def _pixel_arrow(size, diagonal):
    """A small arrow built pixel by pixel (under 11 LEDs, where smoothing
    only blurs it): pointing up, or up-right if diagonal. Its corners are
    trimmed so it still reads as rounded."""
    n = size
    y, x = np.mgrid[0:n, 0:n]
    if not diagonal:
        c = n // 2
        head_rows = (n + 1) // 2
        head = (y < head_rows) & (np.abs(x - c) <= y)
        shaft = (y >= head_rows) & (np.abs(x - c) <= max(0, n // 6))
        fill = head | shaft
        fill[head_rows - 1, 0] = fill[head_rows - 1, n - 1] = False      # round the wing tips
    else:
        h = (n - 1) // 2                                     # the head's leg length
        head = ((n - 1 - x) + y <= h + 1) & (x >= n - 2 - h) & (y <= h + 1)
        shaft = np.abs(x + y - (n - 1)) <= max(1, n // 10)    # 3 LEDs wide up to 19
        shaft &= (x <= n - 2) & (y >= 1)
        fill = head | shaft
        fill[0, n - 1] = False                               # round the point a touch
    return fill


@lru_cache(maxsize=64)
def _arrow(size, direction):
    """An arrow sprite: (fill, outline) masks, size x size. Small ones are
    built pixel by pixel; bigger ones are drawn
    eight times bigger, its corners softened, turned to point the way, then
    shrunk to LED size."""
    from PIL import ImageFilter
    if size < 11 or len(direction) == 2:                    # diagonals: always pixel-built
        turns = {"N": 0, "W": 1, "S": 2, "E": 3, "NE": 0, "NW": 1, "SW": 2, "SE": 3}[direction]
        fill = np.rot90(_pixel_arrow(size, len(direction) == 2), turns)
        pad = np.pad(fill, 1)
        inner = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
        return fill.copy(), (fill & ~inner).copy()
    k = 8
    big = size * k
    img = Image.new("L", (big, big))
    d = ImageDraw.Draw(img)
    c = big / 2
    # Kept inside a circle round the middle, so turning it 45 degrees for a
    # diagonal never clips it: tip at the top of the circle, wings and tail
    # inside it.
    r = big * 0.48
    tip, wing, tail = c - r, c + r * 0.10, c + r * 0.95
    half_w = r * 0.88                                        # the head's half-width
    stem = r * 0.24                                          # the stem's half-width
    d.polygon([(c, tip), (c + half_w, wing), (c + stem, wing), (c + stem, tail),
               (c - stem, tail), (c - stem, wing), (c - half_w, wing)], fill=255)
    img = img.filter(ImageFilter.GaussianBlur(big * 0.045)).point(lambda v: 255 if v > 110 else 0)
    img = img.rotate(_ANGLE[direction], resample=Image.BICUBIC)
    small = np.asarray(img.resize((size, size), Image.BOX), dtype=float) / 255
    fill = small > 0.45
    pad = np.pad(fill, 1)
    inner = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    return fill, fill & ~inner


class _Dance:
    def __init__(self):
        self.arrows = []                                     # [lane, y (float, from the top)]
        self.avg = np.zeros(8)
        self.cool = np.zeros(8)                              # frames until a lane may fire again
        self.flash = np.zeros(8)


def _lane_levels(levels, lanes):
    lv = np.asarray(levels, dtype=float)
    return np.array([g.max() if len(g) else 0.0 for g in np.array_split(lv, lanes)])


def draw_dance(levels, peaks, width, height, field, peak_colour, show_peaks=True, still=False, lanes_n=4):
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # eight lanes need room: at least 7 LEDs each, or it's four
    lanes_n = 8 if lanes_n == 8 and width / 8 >= 7 else 4
    names = DANCE_LANES[lanes_n]
    lane_w = width / lanes_n
    size = int(max(5, min(lane_w - 1, height / 4)))
    size -= (size % 2 == 0)                                  # odd, so the arrow has a middle
    top = 1
    speed = max(1.0, height / 40)                            # rows per frame: about a second to cross
    n = field.shape[1]
    rows = len(field) - 1
    lanes = _lane_levels(levels, lanes_n)
    if still:
        st = _Dance()
        rng = np.random.default_rng(4)
        for lane in range(lanes_n):                                # a made-up few beats for the still
            for k in range(3):
                if rng.random() < 0.55 + 0.4 * lanes[lane]:
                    st.arrows.append([lane, top + size + 4 + k * (height - size) / 3 + lane * 3])
        st.flash[:lanes_n] = (lanes > 0.5) * 6
    else:
        key = (width, height, lanes_n)
        st = _dance.get(key)
        if st is None:
            _dance.clear()
            st = _dance[key] = _Dance()
        # a lane "hits" when it jumps well above its own recent level
        for lane in range(lanes_n):
            v = lanes[lane]
            if st.cool[lane] <= 0 and v > 0.25 and v > st.avg[lane] * 1.35 + 0.06:
                st.arrows.append([lane, float(height)])
                st.cool[lane] = math.ceil((size + 2) / speed)    # the last arrow clears first: no overlaps
            st.avg[lane] = 0.9 * st.avg[lane] + 0.1 * v
        st.cool -= 1
        for a in st.arrows:
            a[1] -= speed
        for a in st.arrows:
            if a[1] <= top:
                st.flash[a[0]] = 6
        st.arrows = [a for a in st.arrows if a[1] > top]
        st.flash = np.maximum(st.flash - 1, 0)

    def colour(lane, bright):
        i = min(n - 1, int((lane + 0.5) / lanes_n * n))
        return field[int(bright * rows), i]

    def stamp(mask, x0, y0, col):
        h, w = mask.shape
        ys, xs = np.nonzero(mask)
        ys, xs = ys + y0, xs + x0
        ok = (ys >= 0) & (ys < height) & (xs >= 0) & (xs < width)
        img[ys[ok], xs[ok]] = np.asarray(col).astype(np.uint8)

    for lane, direction in enumerate(names):
        x0 = int(round(lane * lane_w + (lane_w - size) / 2))
        fill, edge = _arrow(size, direction)
        # the target: an outline, lit up while an arrow arrives
        f = st.flash[lane] / 6
        if f > 0:
            stamp(fill, x0, top, colour(lane, 1.0) * (0.35 + 0.65 * f))
        stamp(edge, x0, top, np.maximum(colour(lane, 0.6) * 0.5, 40) if f == 0 else colour(lane, 1.0))
    for lane, y in st.arrows:
        x0 = int(round(lane * lane_w + (lane_w - size) / 2))
        fill, edge = _arrow(size, names[lane])
        stamp(fill, x0, int(round(y)), colour(lane, 0.75))
        stamp(edge, x0, int(round(y)), np.minimum(255, colour(lane, 1.0) * 1.1 + 25))
    return Image.fromarray(img, "RGB")


def draw(style, levels, peaks, width, height, field, peak_colour=None, show_peaks=True, still=False,
         wave=None, dance_lanes=4):
    """Draw one frame in the named style. Unknown names fall back to sunset.
    still=True is for a single picture (the web panel's style picker), where
    the waterfall and trails have no real history to show and make one up.
    wave is the raw sound (the scope draws it; the others ignore it)."""
    if style == "bars":
        return render(levels, peaks, width, height, show_peaks=show_peaks,
                      field=field, peak_colour=peak_colour)
    if style == "waterfall":
        return draw_waterfall(levels, peaks, width, height, field, peak_colour, show_peaks, still)
    if style == "dance":
        return draw_dance(levels, peaks, width, height, field, peak_colour, show_peaks, still, lanes_n=dance_lanes)
    if style == "trails":
        return draw_trails(levels, peaks, width, height, field, peak_colour, show_peaks, still)
    if style == "scope":
        return draw_scope(levels, peaks, width, height, field, peak_colour, show_peaks, wave)
    if style == "plasma":
        return draw_plasma(levels, peaks, width, height, field, peak_colour, show_peaks,
                           t=12.0 if still else None)
    fn = {"sunset": draw_sunset, "disc": draw_disc, "meter": draw_meter,
          "equals": draw_equals, "mirror": draw_mirror, "wave": draw_wave,
          "vu": draw_vu, "analyser": draw_analyser, "ledring": draw_ledring,
          "ring": draw_ring, "dots": draw_dots}.get(style, draw_sunset)
    return fn(levels, peaks, width, height, field, peak_colour, show_peaks)


# A pleasing, fixed set of levels for previews (web panel style picker, docs).
def sample_levels(n):
    x = np.linspace(0, 1, n)
    levels = 0.35 + 0.45 * np.exp(-((x - 0.18) / 0.16) ** 2) + 0.25 * np.sin(x * 11) ** 2 * (1 - x)
    levels = np.clip(levels, 0.05, 0.95)
    peaks = np.clip(levels + 0.08 + 0.06 * np.cos(x * 7), 0, 1)
    return levels, peaks
