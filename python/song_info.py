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
SCROLL_PX_S = 18             # slow enough to read across a room
CHANGE_SHOW_S = 8.0          # "when the song changes": at least this long

# The words are drawn over the picture, each letter with a dark edge so it
# reads on top of anything. Three sizes, all pixel fonts with every LED on
# or off (fonts/README.md says where each comes from and its licence):
#   small   Tom Thumb, 6 rows: about 16 letters across a 64-wide panel
#   medium  X11 5x7, 7 rows: about 10 letters (the default)
#   large   ChicagoFLF, 14 rows: the original Macintosh lettering
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
TEXT_SIZES = {"small": ("tom-thumb.pil", None), "medium": ("5x7.pil", None),
              "large": ("ChicagoFLF.ttf", 12)}
_fonts = {}


def _font(size):
    """(font, top row, rows): the font, and the band of rows its letters use,
    from the tallest accent to the lowest descender, so every line sits on
    the same baseline."""
    size = size if size in TEXT_SIZES else "medium"
    if size not in _fonts:
        name, px = TEXT_SIZES[size]
        try:
            path = os.path.join(FONT_DIR, name)
            font = ImageFont.truetype(path, px) if px else ImageFont.load(path)
        except OSError:                                  # the file missing
            font = (ImageFont.load_default_imagefont() if hasattr(ImageFont, "load_default_imagefont")
                    else ImageFont.load_default())
        rows = _draw(font, "\u00c5\u00c9\u00d6gjpqy|", 40).any(axis=1).nonzero()[0]
        _fonts[size] = (font, int(rows.min()), int(rows.max() - rows.min() + 1))
    return _fonts[size]


def _draw(font, text, height):
    w = max(1, int(font.getbbox(text)[2]) + 1) if text else 1
    im = Image.new("1", (w, height))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"                                          # no smoothing
    d.text((0, 0), text, font=font, fill=1)
    return np.asarray(im, dtype=bool)


def _printable(text):
    """The fonts know Latin-1 (é, ü, ß, Å...). Anything else: the nearest
    plain letter (ł -> l), a plain dash or quote, or left out."""
    swaps = {"\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
             "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u00a0": " ",
             "\u0141": "L", "\u0142": "l", "\u0152": "OE", "\u0153": "oe"}
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


def text_mask(text, size="medium"):
    """The words as a True/False array, one row per LED row."""
    font, top, rows = _font(size)
    m = _draw(font, text, top + rows + 2)[top:top + rows]
    cols = np.nonzero(m.any(axis=0))[0]
    return m[:, cols.min():cols.max() + 1] if len(cols) else m[:, :1]   # no blank edges


def _grow(m):
    """The mask and every LED touching it: the dark edge round each letter."""
    p = np.pad(m, 1)
    out = p.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out[max(0, dy):p.shape[0] + min(0, dy), max(0, dx):p.shape[1] + min(0, dx)] |= \
                p[max(0, -dy):p.shape[0] - max(0, dy), max(0, -dx):p.shape[1] - max(0, dx)]
    return out


def text_colour(field):
    """The theme's upper colour, halfway to white: in keeping, and easy to read."""
    f = np.asarray(field, dtype=float)
    c = f[int((len(f) - 1) * 0.8)].mean(axis=0)
    c = c * 255.0 / max(1.0, c.max())                         # full strength
    return tuple(int(v) for v in np.clip(c + (255 - c) * 0.5, 0, 255))


class Banner:
    """The song's name along the bottom of the panel, over the picture.

    mode "always": the whole time the music plays.
    mode "change": for a few seconds each time the song changes (a long name
    scrolls through once), then gone.
    """

    def __init__(self):
        self.line = self.size = None
        self.mask = None
        self.since = 0.0

    def update(self, song, now, size="medium"):
        line = song_line(song) if song else None
        if line != self.line:
            self.since = now
        if line != self.line or size != self.size:
            self.line, self.size = line, size
            self.mask = text_mask(line, size) if line else None

    def showing(self, mode, width, now):
        if mode == "always":
            return self.mask is not None
        if mode != "change" or self.mask is None:
            return False
        tw = self.mask.shape[1]
        once = (tw + width) / SCROLL_PX_S if tw > width else 0.0
        return now - self.since < max(CHANGE_SHOW_S, once + 1.0)

    def draw(self, img, colour, now):
        """Paint the words over the bottom of img (a PIL image): each letter
        in colour, the LEDs right round it dimmed so it reads over anything,
        the rest of the picture left as it is."""
        a = np.asarray(img).copy()
        h, w = a.shape[:2]
        m = self.mask
        th, tw = m.shape
        if tw <= w:
            x0 = (w - tw) // 2                                  # fits: centred, still
        else:
            # enters from the right, leaves to the left, round again
            x0 = w - int((now - self.since) * SCROLL_PX_S) % (tw + w)
        y0 = h - th - 1                                         # one row of edge below
        for mask, paint in ((_grow(m), None), (np.pad(m, 1), colour)):
            ys, xs = np.nonzero(mask)
            ys, xs = ys + y0 - 1, xs + x0 - 1
            ok = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
            if paint is None:
                a[ys[ok], xs[ok]] = (a[ys[ok], xs[ok]] * 0.15).astype(np.uint8)
            else:
                a[ys[ok], xs[ok]] = np.asarray(paint, dtype=np.uint8)
        return Image.fromarray(a)
