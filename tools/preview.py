#!/usr/bin/env python3
"""
preview.py -- see what the panel will look like, on any computer.

Runs the real analysis and drawing code on the built-in demo pattern (or a
WAV file) and writes an animated GIF, enlarged so each LED is visible.

    python3 tools/preview.py                          # 64x64, vapor
    python3 tools/preview.py --size 128x64 --theme sunset
    python3 tools/preview.py --wav song.wav --seconds 8

Needs numpy and pillow.
"""

import argparse
import os
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from audio_source import DemoSource  # noqa: E402
from render import THEMES, auto_bars, colour_field, peak_colour_for, render  # noqa: E402
from spectrum import Analyzer, BarSmoother  # noqa: E402

FFT = 2048


def load_wav(path):
    with wave.open(path) as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        sys.exit("only 16-bit WAV files are supported")
    x = np.frombuffer(raw, "<i2").reshape(-1, ch).mean(axis=1) / 32768.0
    return x.astype(np.float32), sr


def as_leds(img, scale):
    """Enlarge, drawing each pixel as a round LED on black, like the real panel."""
    w, h = img.size
    out = Image.new("RGB", (w * scale, h * scale))
    d = ImageDraw.Draw(out)
    px = img.load()
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if any(c):
                box = [x * scale, y * scale, (x + 1) * scale - 2, (y + 1) * scale - 2]
                if scale >= 4:
                    d.ellipse([box[0] + 1, box[1] + 1, box[2], box[3]], fill=c)
                else:               # too small for a circle: a square with a gap
                    d.rectangle(box, fill=c)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="64x64", help="WIDTHxHEIGHT: 64x32, 64x64 or 128x64")
    ap.add_argument("--theme", default="vapor", choices=THEMES)
    ap.add_argument("--bars", type=int, default=0)
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--wav")
    ap.add_argument("--scale", type=int, default=6)
    ap.add_argument("--out", default="preview.gif")
    ap.add_argument("--still", help="also save one frame (at this second) as a PNG")
    a = ap.parse_args()

    width, height = (int(v) for v in a.size.lower().split("x"))
    n = a.bars or auto_bars(width)

    if a.wav:
        audio, sr = load_wav(a.wav)
        read = lambda t: audio[max(0, int(t * sr) - FFT): int(t * sr)]  # noqa: E731
    else:
        demo = DemoSource()
        sr = demo.samplerate
        read = lambda t: demo.read(FFT, now=t)  # noqa: E731

    palette = None
    if a.theme == "album":         # stand-in cover: a warm-to-cool gradient
        palette = np.array([[255 * (1 - i / n), 80, 255 * i / n] for i in range(n)])
    field = colour_field(a.theme, n, height, palette)
    analyzer, smoother = Analyzer(sr, n, FFT), BarSmoother(n)
    dt = 1.0 / a.fps
    frames = []
    for i in range(int(a.seconds * a.fps)):
        t = 1.0 + i * dt
        levels, peaks = smoother.update(analyzer.process(read(t), 50, dt), dt)
        frame = render(levels, peaks, width, height, field=field,
                       peak_colour=peak_colour_for(a.theme))
        frames.append(as_leds(frame, a.scale))
        if a.still and abs(t - float(a.still)) < dt / 2:
            frames[-1].save(os.path.splitext(a.out)[0] + ".png")
    frames[0].save(a.out, save_all=True, append_images=frames[1:],
                   duration=int(1000 / a.fps), loop=0)
    print("wrote %s (%d frames, %dx%d panel, %d bars, theme %s)"
          % (a.out, len(frames), width, height, n, a.theme))


if __name__ == "__main__":
    main()
