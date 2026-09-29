#!/usr/bin/env python3
"""
make_logo.py -- builds every Equalize logo file from one geometry.

    python3 image/make_logo.py

The mark: a vaporwave sun setting over a neon grid, except the sun is made of
equaliser bars. Each bar stops a little short of the circle, and a peak cap
hangs where the circle's edge would be, so the sun's outline is traced by
the caps. The wordmark is set in dot-matrix, the way the LED panel draws.

Writes, all in image/:
    icon.svg                the app icon (source of truth)
    icon-16.png ... 512     PNG sizes; favicon.ico
    wordmark.svg            dot-matrix "EQUALIZE", transparent background
    banner.svg / .png       README header: sky, sun, grid, wordmark
and copies the web panel's icons into python/client/static/.

Needs cairosvg (pip install cairosvg) for the PNGs; the SVGs need nothing.
"""

import math
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "..", "python", "client", "static")

# ---- palette (the web panel's CSS uses the same values) ----
NIGHT_TOP = "#2A0E52"
NIGHT_BOTTOM = "#0B0320"
SUN = [(0.0, "#FFF6A0"), (0.38, "#FF9D7A"), (0.7, "#FF5FC8"), (1.0, "#A94BFF")]
GRID = "#2DE2F5"
PINK, PURPLE, CYAN = "#FF5FC8", "#A94BFF", "#2DE2F5"

# ---- the sun, as bars ----
BARS = 9
# how much of the circle each bar fills: a little short, like music, not a chart
FILL = [0.80, 0.93, 0.74, 0.97, 0.88, 1.00, 0.78, 0.91, 0.84]
SLITS = [(0.10, 0.075), (0.25, 0.055), (0.40, 0.035)]   # (centre height above the horizon, thickness), as fractions of r: wider near the horizon


def stops(gid, pairs, x1=0, y1=0, x2=0, y2=1, units=None):
    u = ' gradientUnits="userSpaceOnUse"' if units else ""
    s = "".join('<stop offset="%g" stop-color="%s"/>' % (o, c) for o, c in pairs)
    return '<linearGradient id="%s" x1="%g" y1="%g" x2="%g" y2="%g"%s>%s</linearGradient>' % (
        gid, x1, y1, x2, y2, u, s)


def sun(cx, horizon, r, gid, caps=True, slits=True):
    """Bars forming a half-disc of radius r standing on the horizon, with the
    classic horizontal slits cut through the lower half, over a soft glow."""
    pitch = 2 * r / BARS
    w = pitch * 0.74
    cuts = sorted((horizon - r * h - r * t / 2, horizon - r * h + r * t / 2)
                  for h, t in SLITS) if slits else []
    out = ['<circle cx="%g" cy="%g" r="%g" fill="url(#%s-glow)"/>' % (cx, horizon, r * 1.35, gid),
           '<g fill="url(#%s)">' % gid]
    cap_h = max(1.5, r * 0.045)
    for i in range(BARS):
        x = cx - r + i * pitch + (pitch - w) / 2
        dx = (x + w / 2) - cx
        arc = math.sqrt(max(0.0, r * r - dx * dx))          # circle height at this bar
        top = horizon - (arc * FILL[i] if caps else arc)
        # the bar, split into segments wherever a slit crosses it
        y = top
        for c0, c1 in cuts + [(horizon, horizon)]:
            if c1 <= y:
                continue
            seg_end = max(y, min(c0, horizon))
            if seg_end - y > 0.5:
                rx = min(w * 0.18, 6) if y == top else 0
                out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f"/>'
                           % (x, y, w, seg_end - y, rx))
            y = max(y, c1)
        if caps and FILL[i] < 0.995:
            out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f"/>'
                       % (x, horizon - arc, w, cap_h, cap_h / 2))
    out.append("</g>")
    return "".join(out)


def glow(gid, cx, cy, r):
    return ('<radialGradient id="%s-glow" cx="%g" cy="%g" r="%g" gradientUnits="userSpaceOnUse">'
            '<stop offset="0" stop-color="%s" stop-opacity="0.45"/>'
            '<stop offset="0.55" stop-color="%s" stop-opacity="0.16"/>'
            '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'
            % (gid, cx, cy, r * 1.35, PINK, PURPLE, PURPLE))


def grid(cx, horizon, bottom, left, right, n_rays, n_rows, stroke, opacity):
    """The neon floor: rays from a vanishing point, rows closing up at the horizon."""
    out = ['<g stroke="%s" stroke-width="%g" stroke-linecap="round" fill="none">' % (GRID, stroke)]
    depth = bottom - horizon
    for k in range(n_rows):
        t = ((k + 1) / n_rows) ** 1.9                    # perspective: rows bunch up far away
        y = horizon + depth * t
        out.append('<line x1="%g" y1="%.2f" x2="%g" y2="%.2f" opacity="%.2f"/>'
                   % (left, y, right, y, opacity * (0.35 + 0.65 * t)))
    for k in range(n_rays):
        f = k / (n_rays - 1)
        xb = left + (right - left) * f
        x_far = cx + (xb - cx) * 0.06
        out.append('<line x1="%.2f" y1="%g" x2="%.2f" y2="%g" opacity="%.2f"/>'
                   % (x_far, horizon, cx + (xb - cx) * 2.2, bottom + depth * 1.2, opacity * 0.8))
    out.append("</g>")
    return "".join(out)


def icon_svg(small=False):
    """512 x 512. small=True drops the grid and slits, for 16-32 px."""
    s = 512
    horizon = 330 if not small else 360
    r = 175 if not small else 205
    defs = (stops("night", [(0, NIGHT_TOP), (1, NIGHT_BOTTOM)])
            + stops("sun", SUN, 0, horizon - r, 0, horizon, units=True)
            + glow("sun", 256, horizon, r)
            + '<clipPath id="tile"><rect width="%d" height="%d" rx="112"/></clipPath>' % (s, s))
    body = ['<rect width="%d" height="%d" rx="112" fill="url(#night)"/>' % (s, s),
            '<g clip-path="url(#tile)">']
    if not small:
        body.append(grid(256, horizon, s, -40, s + 40, 13, 6, 5, 0.9))
        body.append('<rect x="0" y="%g" width="%d" height="4" fill="%s" opacity="0.9"/>'
                    % (horizon - 2, s, GRID))
    body.append(sun(256, horizon, r, "sun", caps=True, slits=not small))
    body.append("</g>")
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d"><defs>%s</defs>%s</svg>'
            % (s, s, defs, "".join(body)))


# ---- dot-matrix wordmark ----
GLYPHS = {
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
}


def wordmark_dots(text, x0, y0, pitch, radius, gid):
    out = ['<g fill="url(#%s)">' % gid]
    x = x0
    for ch in text:
        for row, line in enumerate(GLYPHS[ch]):
            for col, c in enumerate(line):
                if c == "#":
                    out.append('<circle cx="%.1f" cy="%.1f" r="%.2f"/>'
                               % (x + col * pitch, y0 + row * pitch, radius))
        x += 6 * pitch
    out.append("</g>")
    return "".join(out)


def wordmark_width(text, pitch):
    return (len(text) * 6 - 1) * pitch


def wordmark_svg():
    pitch, rad = 10, 3.9
    w = wordmark_width("EQUALIZE", pitch)
    h = 7 * pitch
    defs = stops("wm", [(0, PINK), (0.5, PURPLE), (1, CYAN)], 0, 0, w, 0, units=True)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d"><defs>%s</defs>%s</svg>'
            % (w, h, defs, wordmark_dots("EQUALIZE", pitch / 2, pitch / 2, pitch, rad, "wm")))


def banner_svg():
    W, H = 1280, 480
    horizon = 352
    r = 150
    cx = W / 2
    pitch = 13
    wm_w = wordmark_width("EQUALIZE", pitch)
    wm_x = (W - wm_w) / 2
    defs = (stops("sky", [(0, "#12042E"), (0.6, "#3A0F5E"), (1, "#7A1D72")])
            + stops("floor", [(0, "#1A0636"), (1, NIGHT_BOTTOM)])
            + stops("sun", SUN, 0, horizon - r, 0, horizon, units=True)
            + glow("sun", cx, horizon, r)
            + stops("wm", [(0, PINK), (0.5, PURPLE), (1, CYAN)], wm_x, 0, wm_x + wm_w, 0, units=True))
    body = ['<rect width="%d" height="%d" fill="url(#sky)"/>' % (W, horizon),
            '<rect y="%d" width="%d" height="%d" fill="url(#floor)"/>' % (horizon, W, H - horizon),
            sun(cx, horizon, r, "sun"),
            grid(cx, horizon, H, -300, W + 300, 23, 6, 2.2, 0.75),
            '<rect x="0" y="%g" width="%d" height="3" fill="%s"/>' % (horizon - 1.5, W, GRID),
            wordmark_dots("EQUALIZE", wm_x, 44, pitch, 5.0, "wm"),
            '<text x="%g" y="%d" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" '
            'font-size="19" letter-spacing="7" fill="#F3E9FF" opacity="0.8">YOUR MUSIC, ON THE WALL</text>'
            % (W / 2, 44 + 7 * pitch + 18)]
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d"><defs>%s</defs>%s</svg>'
            % (W, H, defs, "".join(body)))


def write(name, text):
    path = os.path.join(HERE, name)
    with open(path, "w") as f:
        f.write(text)
    return path


def main():
    big = write("icon.svg", icon_svg())
    small = write("icon-small.svg", icon_svg(small=True))
    write("wordmark.svg", wordmark_svg())
    banner = write("banner.svg", banner_svg())
    try:
        import cairosvg
    except ImportError:
        print("SVGs written. Install cairosvg for the PNGs.")
        return
    for px in (16, 32, 64, 128, 180, 192, 256, 512):
        src = small if px <= 32 else big
        cairosvg.svg2png(url=src, write_to=os.path.join(HERE, "icon-%d.png" % px),
                         output_width=px, output_height=px)
    cairosvg.svg2png(url=banner, write_to=os.path.join(HERE, "banner.png"), output_width=1280)
    from PIL import Image
    Image.open(os.path.join(HERE, "icon-32.png")).save(
        os.path.join(HERE, "favicon.ico"), sizes=[(16, 16), (32, 32)])
    os.makedirs(STATIC, exist_ok=True)
    for name, dest in (("favicon.ico", "favicon.ico"), ("icon-180.png", "apple-touch-icon.png"),
                       ("icon-192.png", "icon-192.png"), ("icon-512.png", "icon-512.png"),
                       ("icon.svg", "icon.svg"), ("wordmark.svg", "wordmark.svg")):
        shutil.copy(os.path.join(HERE, name), os.path.join(STATIC, dest))
    print("written to image/ and python/client/static/")


if __name__ == "__main__":
    main()
