"""
song_info.py -- the name of the song playing, and drawing it on the panel.

Where the name comes from:

  AirPlay   shairport-sync passes on what the phone says is playing, and
            the cover (Apple Music, Spotify and most apps send them) through a named pipe,
            /tmp/shairport-sync-metadata, once it is built with
            --with-metadata and its config has metadata switched on (both
            done by install_pi.sh). AirPlayMeta reads that pipe.
  Spotify   the Spotify login (getSongInfo.py), when Spotify is what's
            playing -- including on the Spotify Connect route.

Each item in the pipe looks like
    <item><type>636f7265</type><code>6d696e6d</code><length>5</length>
    <data encoding="base64">
    SGVsbG8=</data></item>
where type and code are four letters written in hex ("core", "minm" =
the song's name). Only a handful matter here; the rest are skipped.
"""

import base64
import os
import re
import select
import threading
import time
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFont

META_PIPE = "/tmp/shairport-sync-metadata"

_ITEM = re.compile(rb"<item><type>([0-9a-f]{1,8})</type><code>([0-9a-f]{1,8})</code>"
                   rb"<length>(\d+)</length>(?:\s*<data encoding=\"base64\">\s*(.*?)</data>)?\s*</item>",
                   re.S)


def _four(hexstr):
    return bytes.fromhex(hexstr.decode().rjust(8, "0")).decode("latin-1")


def parse_items(buf):
    """(type, code, bytes) for every whole item in buf, and what's left over."""
    items, end = [], 0
    for m in _ITEM.finditer(buf):
        data = base64.b64decode(m.group(4)) if m.group(4) else b""
        items.append((_four(m.group(1)), _four(m.group(2)), data))
        end = m.end()
    rest = buf[end:]
    if len(rest) > 8 << 20:                  # far bigger than any cover: something's wrong
        rest = b""
    return items, rest


class AirPlayMeta:
    """What the AirPlay sender says is playing. .song is (title, artist) or None."""

    def __init__(self, path=META_PIPE):
        self.path = path
        self.title = self.artist = None
        self.cover = None                       # the sleeve, as a PIL image, when sent
        self.playing = False
        self._stop = False
        threading.Thread(target=self._reader, daemon=True).start()

    @property
    def song(self):
        return (self.title, self.artist or "") if self.playing and self.title else None

    def take(self, kind, code, data):
        text = data.decode("utf-8", "replace").strip()
        if kind == "core" and code == "minm":
            self.title = text or None
        elif kind == "core" and code == "asar":
            self.artist = text or None
        elif kind == "ssnc" and code in ("pbeg", "prsm", "mdst"):
            self.playing = True
        elif kind == "ssnc" and code == "PICT" and data:
            try:
                from io import BytesIO
                self.cover = Image.open(BytesIO(data)).convert("RGB")
            except Exception:
                pass                            # not a picture we can read: keep the last
        elif kind == "ssnc" and code == "pend":
            self.playing = False
            self.title = self.artist = self.cover = None

    def _reader(self):
        # Like SpotifySource: opened without waiting, and re-opened if the
        # pipe is made anew (shairport-sync makes it when it starts).
        while not self._stop:
            try:
                fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                time.sleep(2.0)
                continue
            inode, buf = os.fstat(fd).st_ino, b""
            try:
                while not self._stop:
                    ready, _, _ = select.select([fd], [], [], 0.5)
                    if ready:
                        try:
                            data = os.read(fd, 65536)
                        except BlockingIOError:
                            data = None
                        if data:
                            items, buf = parse_items(buf + data)
                            for item in items:
                                self.take(*item)
                            continue
                        time.sleep(0.2)                  # no writer just now
                    try:
                        if os.stat(self.path).st_ino != inode:
                            break
                    except FileNotFoundError:
                        break
            finally:
                os.close(fd)

    def close(self):
        self._stop = True


def cover_art(via, airplay_meta, spotify_info, spotify_art):
    """The sleeve of the music being drawn, or None. Same order as now_playing."""
    air = airplay_meta.cover if airplay_meta is not None and airplay_meta.playing else None
    sp = spotify_art if spotify_info and spotify_info.get("is_playing") else None
    if via == "spotify":
        return sp or air
    return air or sp


def now_playing(via, airplay_meta, spotify_info):
    """(title, artist) for the music being drawn, or None.

    via is where the sound is coming from ("airplay", "spotify" or None).
    The AirPlay sender's own word wins for AirPlay; the Spotify login for
    Spotify Connect. Either is better than nothing when the other is silent.
    """
    air = airplay_meta.song if airplay_meta is not None else None
    sp = None
    if spotify_info and spotify_info.get("is_playing") and spotify_info.get("name"):
        sp = (spotify_info["name"], spotify_info.get("artist") or "")
    if via == "spotify":
        return sp or air
    return air or sp


# ---------------------------------------------------------------- drawing
STRIP_H = 12                 # the font's 11 rows, and one dark row above
SCROLL_PX_S = 18             # slow enough to read across a room
CHANGE_SHOW_S = 8.0          # "when the song changes": at least this long


def _font():
    # Pillow's own pixel font: one colour, no smoothing, so every LED is
    # either on or off. Latin-1 only (see _printable).
    if hasattr(ImageFont, "load_default_imagefont"):
        return ImageFont.load_default_imagefont()
    return ImageFont.load_default()


_FONT = None


def _printable(text):
    """The font knows Latin-1 (é, ü, ß, Å...). Anything else: the nearest
    plain letter (ł -> l), a plain dash or quote, or left out."""
    swaps = {"–": "-", "—": "-", "‘": "'", "’": "'",
             "“": '"', "”": '"', "…": "...", " ": " ",
             "Ł": "L", "ł": "l", "Œ": "OE", "œ": "oe"}
    out = []
    for ch in text:
        ch = swaps.get(ch, ch)
        if all(ord(c) < 256 for c in ch):
            out.append(ch)
            continue
        plain = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
        out.append(plain)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def song_line(song):
    title, artist = song
    return _printable("%s - %s" % (title, artist) if artist else title)


def text_mask(text):
    """The words as a True/False array, one row per LED row (11 high)."""
    global _FONT
    if _FONT is None:
        _FONT = _font()
    w = max(1, int(_FONT.getbbox(text)[2])) if text else 1
    im = Image.new("1", (w, 11))
    ImageDraw.Draw(im).text((0, 0), text, font=_FONT, fill=1)
    return np.asarray(im, dtype=bool)


def text_colour(field):
    """The theme's upper colour, halfway to white: in keeping, and easy to read."""
    f = np.asarray(field, dtype=float)
    c = f[int((len(f) - 1) * 0.8)].mean(axis=0)
    c = c * 255.0 / max(1.0, c.max())                         # full strength
    return tuple(int(v) for v in np.clip(c + (255 - c) * 0.5, 0, 255))


class Banner:
    """The song's name along the bottom of the panel.

    mode "always": a strip the whole time; the picture is drawn above it.
    mode "change": over the picture for a few seconds each time the song
    changes (long names scroll through once), then gone.
    """

    def __init__(self):
        self.line = None
        self.mask = None
        self.since = 0.0

    def update(self, song, now):
        line = song_line(song) if song else None
        if line != self.line:
            self.line, self.since = line, now
            self.mask = text_mask(line) if line else None

    def showing(self, mode, width, now):
        if mode == "always":
            return self.mask is not None
        if mode != "change" or self.mask is None:
            return False
        tw = self.mask.shape[1]
        once = (tw + width) / SCROLL_PX_S if tw > width else 0.0
        return now - self.since < max(CHANGE_SHOW_S, once + 1.0)

    def draw(self, img, colour, now):
        """Paint the strip into the bottom rows of img (a PIL image)."""
        a = np.asarray(img).copy()
        h, w = a.shape[:2]
        top = h - STRIP_H
        a[top:] = 0
        m = self.mask
        tw = m.shape[1]
        if tw <= w:
            x0 = (w - tw) // 2                                  # fits: centred, still
            a[top + 1:, x0:x0 + tw][m] = colour
        else:
            # enters from the right, leaves to the left, round again
            gap = w
            off = int((now - self.since) * SCROLL_PX_S) % (tw + gap)
            xs = np.arange(w) + off - w
            ok = (xs >= 0) & (xs < tw)
            cols = np.zeros((11, w), dtype=bool)
            cols[:, ok] = m[:, xs[ok]]
            a[top + 1:][cols] = colour
        return Image.fromarray(a)
