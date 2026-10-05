import base64
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from song_info import (AirPlayMeta, Banner, now_playing, parse_items,  # noqa: E402
                       song_line, text_mask)


def item(kind, code, text=None):
    h = lambda s: s.encode().hex().encode()  # noqa: E731
    out = b"<item><type>%s</type><code>%s</code><length>%d</length>" % (
        h(kind), h(code), len(text.encode()) if text else 0)
    if text is not None:
        out += b'\n<data encoding="base64">\n' + base64.b64encode(text.encode()) + b"</data>"
    return out + b"</item>\n"


def test_parse_items_reads_whole_items_and_keeps_the_rest():
    buf = item("ssnc", "mdst") + item("core", "minm", "Déjà Vu") + item("core", "asar", "Beyoncé")
    half = item("core", "asal", "B'Day")[:20]
    items, rest = parse_items(buf + half)
    assert items == [("ssnc", "mdst", b""), ("core", "minm", "Déjà Vu".encode()),
                     ("core", "asar", "Beyoncé".encode())]
    assert rest.strip() == half


def test_airplay_meta_follows_the_song_and_forgets_it_at_the_end():
    m = AirPlayMeta(path="/nonexistent/pipe")
    for it in parse_items(item("ssnc", "pbeg") + item("core", "minm", "Song")
                          + item("core", "asar", "Band"))[0]:
        m.take(*it)
    assert m.song == ("Song", "Band")
    m.take("ssnc", "pend", b"")
    assert m.song is None
    m.close()


def test_now_playing_prefers_the_source_that_is_playing():
    class Meta:
        song = ("Air song", "Air artist")
    sp = {"is_playing": True, "name": "Sp song", "artist": "Sp artist"}
    assert now_playing("airplay", Meta(), sp) == ("Air song", "Air artist")
    assert now_playing("spotify", Meta(), sp) == ("Sp song", "Sp artist")
    assert now_playing("airplay", None, sp) == ("Sp song", "Sp artist")
    assert now_playing(None, None, {"is_playing": False, "name": "x"}) is None


def test_song_line_makes_any_name_printable():
    assert song_line(("Kraków – Łódź", "Sigur Rós")) == "Kraków - Lódz - Sigur Rós"
    assert song_line(("東京", "")) == ""                      # unprintable letters are left out, no crash
    assert text_mask("Hello").shape[0] >= 6


def test_banner_is_drawn_over_the_picture_and_centres_a_short_name():
    b = Banner()
    b.update(("Hi", ""), now=0.0)
    img = b.draw(Image.new("RGB", (64, 64), (50, 50, 50)), (255, 0, 0), now=0.0)
    a = np.asarray(img)
    assert (a[:48] == 50).all()                               # well above the words: untouched
    lit = np.nonzero(a[:, :, 0] == 255)[1]
    assert abs((lit.min() + lit.max()) / 2 - 31.5) <= 1     # centred
    assert (a[60, :20] == 50).all()                           # beside the words: still the picture
    assert ((a == 7).all(axis=2)).any()                       # a dark edge round the letters (50 * 0.15)


def test_banner_scrolls_a_long_name():
    b = Banner()
    b.update(("A song with a very long name indeed", "Somebody"), now=10.0)
    first = np.asarray(b.draw(Image.new("RGB", (64, 64)), (255, 0, 0), now=11.0))
    later = np.asarray(b.draw(Image.new("RGB", (64, 64)), (255, 0, 0), now=12.0))
    assert first.any() and not (first == later).all()       # it moves


def test_text_sizes():
    heights = {size: text_mask("Déjà Vu", size).shape[0] for size in ("small", "medium", "large")}
    assert heights["small"] < heights["medium"] < heights["large"]
    widths = {size: text_mask("Mr. Brightside", size).shape[1] for size in ("small", "medium", "large")}
    assert widths["small"] < widths["medium"] < widths["large"]
    assert text_mask("x", "nonsense").shape == text_mask("x", "medium").shape


def test_banner_on_change_shows_for_a_while_then_goes():
    b = Banner()
    b.update(("Hi", "Yo"), now=100.0)
    assert b.showing("change", 64, 101.0)
    assert not b.showing("change", 64, 120.0)
    assert b.showing("always", 64, 120.0)
    assert not b.showing("off", 64, 101.0)


def test_airplay_cover_is_read_and_preferred_for_airplay():
    import io
    from song_info import cover_art
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 30, 30)).save(buf, "JPEG")
    m = AirPlayMeta(path="/nonexistent/pipe")
    m.take("ssnc", "pbeg", b"")
    m.take("ssnc", "PICT", buf.getvalue())
    assert m.cover is not None and m.cover.size == (8, 8)
    sp_art = Image.new("RGB", (8, 8), (0, 0, 255))
    playing = {"is_playing": True}
    assert cover_art("airplay", m, playing, sp_art) is m.cover
    assert cover_art("spotify", m, playing, sp_art) is sp_art
    m.take("ssnc", "pend", b"")
    assert cover_art("airplay", m, {"is_playing": False}, sp_art) is None
    m.close()
