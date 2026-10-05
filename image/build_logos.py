#!/usr/bin/env python3
"""
build_logos.py -- the three Equalize logos, and every file made from them.

    python3 image/build_logos.py

    ledring  (default) a ring of LEDs, lit outward further where the music is
             louder: the Ring's shape built from the LED grid's dots
    ring     a ring of rays, longer where it's louder, in teal
    led      the panel itself: warm-white LEDs lit in columns

The control panel lets you pick one (Logo, at the bottom of the page); it
becomes the page's icon, the phone home-screen icon and the browser-tab icon.

At 32 px and below the LED ring is drawn with fewer, bigger dots, because the
full one turns to mush at that size.

Writes image/logos/<key>/{icon.svg, icon-512/192/180/64/32/16.png, favicon.ico},
copies the default to python/client/static/, and redraws image/banner.png.
Needs cairosvg and Pillow.
"""
import math
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "logos")
STATIC = os.path.join(HERE, "..", "python", "client", "static")
FONT = os.path.join(HERE, "fonts", "BarlowSemiCondensed-Bold.ttf")
DEFAULT = "ledring"
LOGOS = ("ledring", "ring", "led")
WARM, UNLIT, GROUND = "#FFF3DE", "#2A2724", "#141210"
UNLIT_DOT = "#211E1B"          # the LED ring's unlit dots: big, so quieter than the grid's
TEAL, DEEP = "#3FE0C5", "#0B1F2A"


def tile(bg, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
            '<defs><clipPath id="t"><rect width="512" height="512" rx="112"/></clipPath></defs>'
            '<rect width="512" height="512" rx="112" fill="%s"/>'
            '<g clip-path="url(#t)">%s</g></svg>' % (bg, body))


def loudness(a):
    """The made-up spectrum every logo draws: same shape in all three."""
    return (0.5 + 0.5 * math.sin(3 * a + 0.6)) * (0.6 + 0.4 * math.cos(5 * a))


def ledring(small=False):
    """Rings of dots that grow as they go out: each circle's dots are bigger
    than the last, so the ring opens out like a ripple."""
    n_rays, n_rings = (12, 3) if small else (24, 5)
    out = []
    # radius of each ring, and of its dots: both grow outward
    if small:
        radii, dots = (104, 162, 228), (17, 23, 30)
    else:
        radii, dots = (88, 118, 152, 190, 232), (7, 9.5, 12, 14.5, 17)
    for k in range(n_rays):
        a = 2 * math.pi * k / n_rays - math.pi / 2
        # the inner third always lit (the ring itself), the rest by loudness
        base = 1 if small else 2
        lit = base + round((n_rings - base) * loudness(a + math.pi / 2))
        for j in range(n_rings):
            r = radii[j]
            out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>'
                       % (256 + r * math.cos(a), 256 + r * math.sin(a), dots[j], WARM if j < lit else UNLIT_DOT))
    return tile(GROUND, "".join(out))


def ring(small=False):
    """Rays round a circle, longer where it's louder, and widening as they go
    out: each one a thin wedge from the circle."""
    out = []
    n = 18 if small else 36
    r0 = 96
    w0, grow = (12, 0.10) if small else (9, 0.06)       # a gentle taper: about 1.5x wider at the tip       # width at the circle, and per unit of length
    for k in range(n):
        a = 2 * math.pi * k / n
        length = 50 + 70 * loudness(a)
        r1 = r0 + length
        w1 = w0 + grow * length
        ca, sa = math.cos(a), math.sin(a)
        px, py = -sa, ca                                  # across the ray
        pts = [(256 + r0 * ca + px * w0 / 2, 256 + r0 * sa + py * w0 / 2),
               (256 + r1 * ca + px * w1 / 2, 256 + r1 * sa + py * w1 / 2),
               (256 + r1 * ca - px * w1 / 2, 256 + r1 * sa - py * w1 / 2),
               (256 + r0 * ca - px * w0 / 2, 256 + r0 * sa - py * w0 / 2)]
        out.append('<polygon points="%s" fill="%s" stroke="%s" stroke-width="2" stroke-linejoin="round"/>'
                   % (" ".join("%.1f,%.1f" % p for p in pts), TEAL, TEAL))
    out.append('<circle cx="256" cy="256" r="58" fill="none" stroke="%s" stroke-width="%d"/>' % (TEAL, 22 if small else 14))
    return tile(DEEP, "".join(out))


def led(small=False):
    n, heights = 6, (3, 5, 4, 6, 2, 4)
    if small:
        n, heights = 4, (2, 4, 3, 1)
    pitch = 300 / n
    x0 = (512 - pitch * (n - 1)) / 2
    y_bottom = 256 + pitch * (n - 1) / 2
    out = []
    for c in range(n):
        for rr in range(n):
            out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>'
                       % (x0 + c * pitch, y_bottom - rr * pitch, pitch * 0.36,
                          WARM if rr < heights[c] else UNLIT))
    return tile(GROUND, "".join(out))


DRAW = {"ledring": ledring, "ring": ring, "led": led}


def build():
    import cairosvg
    from PIL import Image
    for key in LOGOS:
        d = os.path.join(OUT, key)
        os.makedirs(d, exist_ok=True)
        big, small = DRAW[key](), DRAW[key](small=True)
        open(os.path.join(d, "icon.svg"), "w").write(big)
        for px in (512, 192, 180, 64, 32, 16):
            src = small if px <= 32 else big
            cairosvg.svg2png(bytestring=src.encode(), write_to=os.path.join(d, "icon-%d.png" % px),
                             output_width=px, output_height=px)
        ico = Image.open(os.path.join(d, "icon-32.png"))
        ico.save(os.path.join(d, "favicon.ico"), sizes=[(16, 16), (32, 32)])
    src = os.path.join(OUT, DEFAULT)
    for name, dest in (("icon.svg", "icon.svg"), ("icon-192.png", "icon-192.png"),
                       ("icon-512.png", "icon-512.png"), ("icon-180.png", "apple-touch-icon.png"),
                       ("favicon.ico", "favicon.ico")):
        shutil.copy(os.path.join(src, name), os.path.join(STATIC, dest))
    banner()


def banner():
    """README header: the default logo and the name, on the panel's black."""
    from PIL import Image, ImageDraw, ImageFont
    w, h = 1600, 400
    img = Image.new("RGB", (w, h), (15, 16, 18))
    icon = Image.open(os.path.join(OUT, DEFAULT, "icon-512.png")).convert("RGBA").resize((260, 260), Image.LANCZOS)
    img.paste(icon, (110, 70), icon)
    d = ImageDraw.Draw(img)
    d.text((440, 92), "EQUALIZE", font=ImageFont.truetype(FONT, 150), fill=(242, 236, 222))
    d.text((446, 262), "YOUR MUSIC, ON AN LED PANEL", font=ImageFont.truetype(FONT, 44), fill=(150, 146, 138))
    img.save(os.path.join(HERE, "banner.png"))


if __name__ == "__main__":
    build()
    print("wrote", ", ".join(LOGOS), "and the banner")
