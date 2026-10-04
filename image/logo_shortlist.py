#!/usr/bin/env python3
"""
logo_shortlist.py -- a second round of logo ideas for Equalize, away from
the purple vaporwave look of logo_options.py.

    python3 image/logo_shortlist.py

Writes image/shortlist/<key>.svg, <key>-512/64/32.png and
image/shortlist/sheet.png: every idea at app-icon size and at the sizes a
browser tab and a phone's home screen really use. A logo that only works big
doesn't work.

The ideas lean on hi-fi hardware and the music players of the early 2000s
(Winamp's analyser, a VU meter's needle, a graphic equaliser's sliders)
rather than on any one colour scheme.

Needs cairosvg for the PNGs.
"""

import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "shortlist")


def tile(bg, body, defs=""):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs>%s'
            '<clipPath id="t"><rect width="512" height="512" rx="112"/></clipPath></defs>'
            '<rect width="512" height="512" rx="112" fill="%s"/>'
            '<g clip-path="url(#t)">%s</g></svg>' % (defs, bg, body))


# ---------------------------------------------------------------- 1 analyser
def analyser():
    """Winamp's spectrum analyser: segmented bars, green to yellow to red,
    with a cap hanging above each."""
    heights = [5, 8, 6, 9, 4]                     # segments lit per bar, of 10
    seg_h, gap, bar_w = 26, 8, 62
    x0 = (512 - (5 * bar_w + 4 * 22)) / 2
    base = 410
    out = []
    for i, h in enumerate(heights):
        x = x0 + i * (bar_w + 22)
        for s in range(h):
            y = base - (s + 1) * (seg_h + gap) + gap
            c = "#39D353" if s < 5 else "#F5D547" if s < 8 else "#FF4B3E"
            out.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="5" fill="%s"/>'
                       % (x, y, bar_w, seg_h, c))
        cap_y = base - (h + 1.6) * (seg_h + gap)
        out.append('<rect x="%.1f" y="%.1f" width="%d" height="12" rx="4" fill="#E9EEF2"/>'
                   % (x, cap_y, bar_w))
    return tile("#0D1013", "".join(out))


# ---------------------------------------------------------------- 2 needle
def needle():
    """A VU meter: ivory dial, black needle, the last stretch of the scale in red."""
    cx, cy, r = 256, 360, 210
    out = ['<rect x="44" y="96" width="424" height="320" rx="40" fill="#F3EAD3"/>']
    for k in range(21):
        f = k / 20
        a = math.radians(-50 + 100 * f)
        long_tick = k % 5 == 0
        r1 = r - (34 if long_tick else 20)
        col = "#C8261E" if f > 0.75 else "#1B1B1B"
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%d" stroke-linecap="round"/>'
                   % (cx + r1 * math.sin(a), cy - r1 * math.cos(a),
                      cx + r * math.sin(a), cy - r * math.cos(a), col, 9 if long_tick else 6))
    a = math.radians(-50 + 100 * 0.7)
    out.append('<line x1="%d" y1="%d" x2="%.1f" y2="%.1f" stroke="#111" stroke-width="12" stroke-linecap="round"/>'
               % (cx, cy, cx + (r - 8) * math.sin(a), cy - (r - 8) * math.cos(a)))
    out.append('<circle cx="%d" cy="%d" r="26" fill="#111"/>' % (cx, cy))
    return tile("#1A1A1A", "".join(out))


# ---------------------------------------------------------------- 3 faders
def faders():
    """A graphic equaliser's sliders -- the object the app is named after."""
    xs, knobs = (146, 256, 366), (300, 170, 250)
    out = []
    for x, k in zip(xs, knobs):
        out.append('<rect x="%d" y="86" width="14" height="340" rx="7" fill="#05070A"/>' % (x - 7))
        out.append('<rect x="%d" y="%d" width="96" height="58" rx="12" fill="#EDEFF2"/>' % (x - 48, k - 29))
        out.append('<rect x="%d" y="%d" width="64" height="9" rx="4" fill="#FF7A1A"/>' % (x - 32, k - 4))
    return tile("#2B3036", "".join(out))


# ---------------------------------------------------------------- 4 monogram
def monogram():
    """An E whose three arms are bars of different lengths, like an EQ."""
    out = ['<rect x="118" y="104" width="62" height="304" rx="14" fill="#FFB020"/>']
    for y, length in ((104, 276), (225, 196), (346, 248)):
        out.append('<rect x="118" y="%d" width="%d" height="62" rx="14" fill="#FFB020"/>' % (y, length))
    return tile("#121212", "".join(out))


# ---------------------------------------------------------------- 5 ring
def ring():
    """A ring of rays, longer where the music is louder; no sun in the middle."""
    out = []
    n = 36
    for k in range(n):
        a = 2 * math.pi * k / n
        length = 50 + 70 * (0.5 + 0.5 * math.sin(3 * a + 0.6)) * (0.6 + 0.4 * math.cos(5 * a))
        r0 = 96
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#3FE0C5" stroke-width="15" stroke-linecap="round"/>'
                   % (256 + r0 * math.cos(a), 256 + r0 * math.sin(a),
                      256 + (r0 + length) * math.cos(a), 256 + (r0 + length) * math.sin(a)))
    out.append('<circle cx="256" cy="256" r="58" fill="none" stroke="#3FE0C5" stroke-width="14"/>')
    return tile("#0B1F2A", "".join(out))


# ---------------------------------------------------------------- 6 led
def led():
    """What the panel itself is: a grid of LEDs, lit in columns to different
    heights. One warm white, so it sits quietly in any room."""
    n, heights = 6, (3, 5, 4, 6, 2, 4)
    pitch = 300 / n
    x0 = (512 - pitch * (n - 1)) / 2
    y_bottom = 256 + pitch * (n - 1) / 2
    out = []
    for c in range(n):
        for rr in range(n):
            lit = rr < heights[c]
            out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>'
                       % (x0 + c * pitch, y_bottom - rr * pitch, pitch * 0.36,
                          "#FFF3DE" if lit else "#2A2724"))
    return tile("#141210", "".join(out))


IDEAS = [
    ("analyser", "1  Analyser", "Winamp's analyser: segment bars,\ngreen to yellow to red, peak caps", analyser),
    ("needle", "2  Needle", "A hi-fi VU meter: ivory dial, black\nneedle, the red zone", needle),
    ("faders", "3  Sliders", "A graphic equaliser's sliders: the\nobject the app is named after", faders),
    ("monogram", "4  EQ letter", "An E whose arms are bars of\ndifferent lengths, in amber", monogram),
    ("ring", "5  Ring", "A ring of rays, longer where it's\nlouder; teal on deep blue-green", ring),
    ("led", "6  LED grid", "The panel itself: warm-white LEDs lit\nin columns. Quiet in any room", led),
]


def main():
    import cairosvg
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(OUT, exist_ok=True)
    cell_w, pad = 300, 30
    sheet = Image.new("RGB", (pad + len(IDEAS) * (cell_w + pad), 520), (246, 245, 242))
    d = ImageDraw.Draw(sheet)
    bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    for i, (key, title, blurb, fn) in enumerate(IDEAS):
        svg = fn()
        open(os.path.join(OUT, key + ".svg"), "w").write(svg)
        for px in (512, 64, 32):
            cairosvg.svg2png(bytestring=svg.encode(), write_to=os.path.join(OUT, "%s-%d.png" % (key, px)),
                             output_width=px, output_height=px)
        x = pad + i * (cell_w + pad)
        big = Image.open(os.path.join(OUT, key + "-512.png")).convert("RGBA").resize((cell_w, cell_w), Image.LANCZOS)
        sheet.paste(big, (x, pad), big)
        for j, px in enumerate((64, 32)):
            im = Image.open(os.path.join(OUT, "%s-%d.png" % (key, px))).convert("RGBA")
            sheet.paste(im, (x + j * 80, pad + cell_w + 16), im)
        d.text((x + 128, pad + cell_w + 36), "64 px / 32 px", fill=(110, 110, 110), font=small)
        d.text((x, pad + cell_w + 96), title, fill=(25, 25, 25), font=bold)
        d.multiline_text((x, pad + cell_w + 128), blurb, fill=(90, 90, 90), font=small, spacing=4)
    sheet.save(os.path.join(OUT, "sheet.png"))
    print("wrote", os.path.relpath(OUT))


if __name__ == "__main__":
    main()
