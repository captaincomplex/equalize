#!/usr/bin/env python3
"""
logo_options.py -- five candidate logos for Equalize, side by side.

    python3 image/logo_options.py

Writes image/options/option-<n>.svg (and .png at 512) plus
image/options/sheet.png: every option at 512, 64 and 32 px, so you can
judge each at app-icon size and at browser-tab size.

All five share one palette: night purple, the sun's pale-yellow -> peach ->
pink -> purple, and a cyan accent.
"""

import math
import os

import make_logo as base

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "options")
PINK, PURPLE, CYAN, PEACH, SUN = "#FF5FC8", "#A94BFF", "#2DE2F5", "#FF9D7A", "#FFF6A0"
S = 512


def tile(body, defs=""):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs>%s%s'
            '<clipPath id="tile"><rect width="512" height="512" rx="112"/></clipPath></defs>'
            '<rect width="512" height="512" rx="112" fill="url(#night)"/>'
            '<g clip-path="url(#tile)">%s</g></svg>'
            % (base.stops("night", [(0, base.NIGHT_TOP), (1, base.NIGHT_BOTTOM)]), defs, body))


def mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))


def ramp(stops, t):
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            return mix(c0, c1, (t - p0) / (p1 - p0) if p1 > p0 else 0)
    return stops[-1][1]


# 1. Sunset Bars -- the current logo.
def option_1():
    return base.icon_svg()


# 2. Dot-matrix E -- the letter E drawn in LEDs; its three arms are equaliser
#    bars of different lengths, each with a cyan peak dot hanging beyond it.
def option_2():
    pitch, r = 36, 13.5
    cols, rows = 10, 11
    x0 = (S - (cols - 1) * pitch) / 2 + pitch * 0.25
    y0 = (S - (rows - 1) * pitch) / 2
    arms = {0: 6, 1: 6, 5: 4, 6: 4, 9: 8, 10: 8}          # row -> arm length in dots
    peaks = {0: 8, 5: 6, 9: 9}                            # row -> peak dot column
    dots = []
    for y in range(rows):
        for x in range(cols):
            lit = x < 2 or x < arms.get(y, 0)
            if lit:
                dots.append('<circle cx="%.1f" cy="%.1f" r="%.1f"/>' % (x0 + x * pitch, y0 + y * pitch, r))
    caps = "".join('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>'
                   % (x0 + c * pitch, y0 + (row + 0.5) * pitch, r, CYAN) for row, c in peaks.items())
    grad = base.stops("dotE", [(0, SUN), (0.35, PEACH), (0.65, PINK), (1, PURPLE)], 0, y0, 0, y0 + (rows - 1) * pitch, units=True)
    return tile('<g fill="url(#dotE)">%s</g>%s' % ("".join(dots), caps), grad)


# 3. Spectrum Disc -- a small vaporwave sun at the centre of a record, with
#    the spectrum radiating around it like a ring of light.
def option_3():
    cx = cy = 256
    n = 44
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n - math.pi / 2
        amp = 0.55 + 0.25 * math.sin(3 * a + 0.7) + 0.2 * math.sin(7 * a + 1.9)
        r0, r1 = 128, 128 + 18 + 88 * max(0.05, amp)
        col = ramp([(0, PINK), (0.33, PURPLE), (0.66, CYAN), (1, PINK)], i / n)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="12" stroke-linecap="round"/>'
                   % (cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + r1 * math.cos(a), cy + r1 * math.sin(a), col))
    defs = base.stops("sun", base.SUN, 0, cy - 88, 0, cy + 88, units=True)
    sun = ['<circle cx="256" cy="256" r="104" fill="#12042e" stroke="%s" stroke-opacity=".35" stroke-width="3"/>' % PURPLE,
           '<circle cx="256" cy="256" r="84" fill="url(#sun)"/>']
    for k, (h, t) in enumerate([(30, 7), (52, 10), (72, 13)]):      # slits in the lower half
        sun.append('<rect x="160" y="%d" width="192" height="%d" fill="#12042e"/>' % (cy + h - t / 2, t))
    return tile("".join(out) + "".join(sun), defs)


# 4. Segment Meter -- a hi-fi LED meter: columns of stacked segments, lit up
#    to the music, unlit ones glowing faintly, a cyan segment as the peak.
def option_4():
    heights = [5, 8, 6, 10, 7]
    peak = [7, 10, 8, None, 9]
    cols, segs = 5, 11
    w, gap_x = 62, 18
    h, gap_y = 22, 9
    x0 = (S - (cols * w + (cols - 1) * gap_x)) / 2
    y_bottom = 256 + (segs * (h + gap_y) - gap_y) / 2
    out = []
    for c in range(cols):
        for s in range(segs):
            x = x0 + c * (w + gap_x)
            y = y_bottom - (s + 1) * (h + gap_y) + gap_y
            t = s / (segs - 1)
            col = ramp([(0, PURPLE), (0.4, PINK), (0.75, PEACH), (1, SUN)], t)
            if s < heights[c]:
                out.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="6" fill="%s"/>' % (x, y, w, h, col))
            elif peak[c] is not None and s == peak[c]:
                out.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="6" fill="%s"/>' % (x, y, w, h, CYAN))
            else:
                out.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="6" fill="%s" opacity=".13"/>' % (x, y, w, h, col))
    return tile("".join(out))


# 5. Equals -- EQ as a pun: an equals sign whose two strokes are spectra,
#    pink bars rising above, cyan bars hanging below, mirrored like a reflection.
def option_5():
    n = 11
    w, gap = 26, 9
    x0 = (S - (n * w + (n - 1) * gap)) / 2
    top_h = [44, 70, 96, 62, 118, 88, 108, 58, 84, 50, 36]
    out = []
    for i, hh in enumerate(top_h):
        x = x0 + i * (w + gap)
        out.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="7" fill="url(#up)"/>' % (x, 238 - hh, w, hh))
        low = hh * 0.62
        out.append('<rect x="%.1f" y="274" width="%d" height="%.1f" rx="7" fill="url(#down)"/>' % (x, w, low))
    defs = (base.stops("up", [(0, SUN), (0.5, PINK), (1, PURPLE)], 0, 120, 0, 238, units=True)
            + base.stops("down", [(0, CYAN), (1, "#1B3A8F")], 0, 274, 0, 350, units=True))
    return tile("".join(out), defs)


OPTIONS = [
    ("1  Sunset Bars", "The current logo: a vaporwave sun built from bars", option_1),
    ("2  Dot-matrix E", "An LED letter E; its arms are bars with peak dots", option_2),
    ("3  Spectrum Disc", "A striped sun inside a ring of spectrum, like a record", option_3),
    ("4  Segment Meter", "A hi-fi LED meter, cyan peak segments", option_4),
    ("5  Equals", "EQ as '=': spectrum above, reflection below", option_5),
]


def main():
    import cairosvg
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs(OUT, exist_ok=True)
    pngs = []
    for i, (_, _, fn) in enumerate(OPTIONS, 1):
        svg = os.path.join(OUT, "option-%d.svg" % i)
        with open(svg, "w") as f:
            f.write(fn())
        sizes = {}
        for px in (512, 64, 32):
            p = os.path.join(OUT, "option-%d-%d.png" % (i, px))
            cairosvg.svg2png(url=svg, write_to=p, output_width=px, output_height=px)
            sizes[px] = p
        pngs.append(sizes)

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    cell, big = 330, 280
    sheet = Image.new("RGB", (cell * len(OPTIONS) + 30, 490), (246, 243, 250))
    d = ImageDraw.Draw(sheet)
    for i, ((title, note, _), sizes) in enumerate(zip(OPTIONS, pngs)):
        x = 30 + i * cell
        sheet.paste(Image.open(sizes[512]).convert("RGBA").resize((big, big), Image.LANCZOS), (x, 24),
                    Image.open(sizes[512]).convert("RGBA").resize((big, big), Image.LANCZOS))
        im64 = Image.open(sizes[64]).convert("RGBA")
        im32 = Image.open(sizes[32]).convert("RGBA")
        sheet.paste(im64, (x, 320), im64)
        sheet.paste(im32, (x + 80, 352), im32)
        d.text((x + 128, 330), "64 px / 32 px", font=small, fill=(120, 110, 140))
        d.text((x, 400), title, font=font, fill=(40, 20, 70))
        import textwrap
        d.multiline_text((x, 432), textwrap.fill(note, 34), font=small, fill=(90, 80, 110), spacing=4)
    sheet.save(os.path.join(OUT, "sheet.png"))
    print("wrote image/options/")


if __name__ == "__main__":
    main()
