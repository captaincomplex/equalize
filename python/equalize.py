#!/usr/bin/env python3
"""
equalize.py -- the Equalize display daemon.

Takes the music arriving over AirPlay (see audio_source.py), splits it into
frequency bands and draws them as a bouncing graphic equaliser on the LED
matrix. No microphone: the Pi only ever sees the digital audio your phone
chose to send it.

One always-running process. Settings come from config/state.json (written by
the web panel) and are re-read twice a second, so changes apply without a
restart.

Usage:
    python3 equalize.py [<spotify_username> <path_to_.cache_token>]

Spotify is optional. Without it everything works except the "Spotify only"
mode, the song name on the dashboard and the album-cover colour theme.

Matrix hardware options come from config/rgb_options.ini.
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime
from io import BytesIO

# Runs as root (GPIO), so any __pycache__ it wrote would be root-owned.
sys.dont_write_bytecode = True

import requests
from PIL import Image

from audio_source import DemoSource, MusicSource, SoundDetector
from display_logic import (compute_effective, effective_brightness, panel_config_paths,
                           panel_geometry, read_panel_config)
from render import THEMES, album_palette, auto_bars, colour_field, peak_colour_for
from styles import STYLES, draw as draw_style
from spectrum import Analyzer, BarSmoother
from state import PREVIEW_PATH, read_state, write_status

DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.abspath(os.path.join(DIR, "..", "config", "rgb_options.ini"))

FFT_SIZE = 2048                 # samples per analysis (~43 ms at 48 kHz)
SPOTIFY_POLL_SECONDS = 2.0
STATE_READ_SECONDS = 0.5
PREVIEW_SECONDS = 0.5           # how often the web preview snapshot is refreshed
STATUS_SECONDS = 2.0
SOURCE_RETRY_SECONDS = 10.0

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%d/%m/%Y %H:%M:%S", level=logging.INFO)
log = logging.getLogger("equalize")


def load_matrix():
    from rgbmatrix import RGBMatrix, RGBMatrixOptions   # only exists on the Pi

    d = read_panel_config(panel_config_paths(os.path.dirname(CONFIG_PATH)))
    options = RGBMatrixOptions()
    options.rows = int(d["rows"])
    options.cols = int(d["columns"])
    options.chain_length = int(d.get("chain_length", 1))
    options.parallel = int(d.get("parallel", 1))
    options.hardware_mapping = d.get("hardware_mapping", "adafruit-hat")
    options.gpio_slowdown = int(d.get("gpio_slowdown", 2))
    rotate = panel_geometry(d)[2]
    if rotate:
        options.pixel_mapper_config = "Rotate:%d" % rotate   # the driver turns the picture
    options.brightness = int(d.get("brightness", 60))
    if d.get("refresh_rate"):
        options.limit_refresh_rate_hz = int(d["refresh_rate"])
    options.drop_privileges = False      # stay root to read state.json and the token
    fps = max(10, min(60, int(d.get("fps", 40))))
    return RGBMatrix(options=options), fps


class SpotifyWatcher(threading.Thread):
    """Asks Spotify what's playing every couple of seconds, in the background,
    so a slow network never makes the bars stutter. Also fetches the album
    cover when the track changes (for the "album" colour theme)."""

    def __init__(self, username, token_path):
        super().__init__(daemon=True)
        self.username, self.token_path = username, token_path
        self.info = {"is_playing": False, "image_url": None, "name": None, "artist": None}
        self.art = None
        self._art_url = None

    def run(self):
        from getSongInfo import getSongInfo
        while True:
            info = getSongInfo(self.username, self.token_path)
            url = info.get("image_url")
            if url and url != self._art_url:
                try:
                    resp = requests.get(url, timeout=5)
                    self.art = Image.open(BytesIO(resp.content)).convert("RGB")
                    self._art_url = url
                except Exception as e:
                    log.debug("album art fetch failed: %s", e)
            self.info = info
            time.sleep(SPOTIFY_POLL_SECONDS)


class NoSpotify:
    info = {"is_playing": False, "image_url": None, "name": None, "artist": None}
    art = None


def open_source(state):
    if state.get("audio_source") == "demo":
        return DemoSource()
    return MusicSource()             # AirPlay and Spotify Connect, whichever plays


def save_preview(img):
    tmp = PREVIEW_PATH + ".tmp"
    os.makedirs(os.path.dirname(PREVIEW_PATH), exist_ok=True)
    img.save(tmp, "PNG")
    os.replace(tmp, PREVIEW_PATH)


def _stop_on_sigterm(signum, frame):
    # systemctl stop (e.g. handing the panel to Spotipi Photo) sends SIGTERM;
    # treat it like Ctrl-C so the panel is cleared on the way out.
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, _stop_on_sigterm)
    matrix, fps = load_matrix()
    width, height = matrix.width, matrix.height
    canvas = matrix.CreateFrameCanvas()
    frame_s = 1.0 / fps

    if len(sys.argv) >= 3:
        spotify = SpotifyWatcher(sys.argv[1], sys.argv[2])
        spotify.start()
    else:
        spotify = NoSpotify()
        log.info("no Spotify token given: 'Spotify only' mode and album colours unavailable")

    state = read_state()
    source = open_source(state)
    source_kind = state.get("audio_source")
    last_source_try = time.time()
    detector = SoundDetector()

    analyzer = smoother = field = None
    look_key = None
    shown = "vapor"
    brightness = None
    effective = "off"
    has_sound = False
    dark = False
    last_state_read = last_preview = last_status = 0.0
    last_frame = time.time()
    frame_count, fps_measured, fps_window = 0, 0.0, time.time()

    log.info("equalize started: %dx%d panel, %d fps, source=%s",
             width, height, fps, source.error or source.device_name)

    while True:
        try:
            now = time.time()
            dt = min(0.25, now - last_frame)
            last_frame = now

            # --- always listen, so we notice when music starts ---
            samples = source.read(FFT_SIZE)
            has_sound = detector.update(samples, now)

            # --- settings, twice a second ---
            if now - last_state_read >= STATE_READ_SECONDS:
                last_state_read = now
                state = read_state()

                kind = state.get("audio_source")
                retry = source.error and now - last_source_try >= SOURCE_RETRY_SECONDS
                if kind != source_kind or retry:
                    source.close()
                    source = open_source(state)
                    source_kind, last_source_try = kind, now
                    analyzer = None
                    log.info("sound source: %s", source.error or source.device_name)

                b = effective_brightness(state, datetime.now())
                if b != brightness:
                    brightness = b
                    matrix.brightness = b
                    canvas.brightness = b

                effective = compute_effective(state, has_sound, spotify.info["is_playing"],
                                              now_epoch=now)

            # --- dark: clear once, then idle cheaply ---
            if effective == "off":
                if not dark:
                    matrix.Clear()
                    canvas.Clear()
                    dark = True
                    save_preview(Image.new("RGB", (width, height)))
            else:
                dark = False
                n_bars = int(state.get("bars") or 0) or auto_bars(width)
                n_bars = max(4, min(n_bars, width))
                if analyzer is None or analyzer.n_bars != n_bars \
                        or analyzer.samplerate != source.samplerate:
                    analyzer = Analyzer(source.samplerate, n_bars, FFT_SIZE)
                    smoother = BarSmoother(n_bars)
                    look_key = None

                theme = state.get("theme", "mono")
                theme = theme if theme in THEMES else "mono"
                new_look = (theme, n_bars, id(spotify.art) if theme == "album" else None)
                if new_look != look_key:
                    palette = album_palette(spotify.art, n_bars) if theme == "album" else None
                    # "album" with no usable cover (no Spotify, or a black-and-white
                    # sleeve) falls back to rainbow rather than going blank
                    shown = "rainbow" if theme == "album" and palette is None else theme
                    field = colour_field(shown, n_bars, height, palette)
                    look_key = new_look

                target = analyzer.process(samples, state.get("sensitivity", 50), dt)
                levels, peaks = smoother.update(target, dt)
                style = state.get("style", "ledring")
                img = draw_style(style if style in STYLES else "ledring", levels, peaks,
                                 width, height, field, peak_colour=peak_colour_for(shown),
                                 show_peaks=bool(state.get("peaks", True)), wave=samples,
                                 dance_lanes=int(state.get("dance_lanes", 4)))
                canvas.SetImage(img)
                canvas = matrix.SwapOnVSync(canvas)

                if now - last_preview >= PREVIEW_SECONDS:
                    last_preview = now
                    save_preview(img)

            # --- status for the web dashboard ---
            frame_count += 1
            if now - fps_window >= 2.0:
                fps_measured = frame_count / (now - fps_window)
                frame_count, fps_window = 0, now
            if now - last_status >= STATUS_SECONDS:
                last_status = now
                info = spotify.info
                write_status({
                    "effective": effective,
                    "has_sound": has_sound,
                    "via": getattr(source, "via", None),      # "airplay", "spotify" or None
                    "spotify_enabled": not isinstance(spotify, NoSpotify),
                    "is_playing": bool(info.get("is_playing")),
                    "song": info.get("name"),
                    "artist": info.get("artist"),
                    "brightness": brightness,
                    "panel": "%dx%d" % (width, height),
                    "fps": round(fps_measured, 1),
                    "source": source_kind,
                    "source_device": source.device_name,
                    "source_error": source.error,
                    "bars": analyzer.n_bars if analyzer else None,
                })

            # --- pace the loop (slower while dark, but still listening) ---
            spare = (0.1 if effective == "off" else frame_s) - (time.time() - now)
            if spare > 0:
                time.sleep(spare)

        except KeyboardInterrupt:
            matrix.Clear()
            source.close()
            sys.exit(0)
        except Exception as e:
            log.warning("loop error: %s", e)
            time.sleep(1)


if __name__ == "__main__":
    main()
