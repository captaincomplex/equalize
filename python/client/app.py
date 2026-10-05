#!/usr/bin/env python3
"""
app.py -- Equalize web control panel.

Writes config/state.json, which the always-running display daemon reads
twice a second. No service restarts involved, so changes are instant.

Port 80 by default; set EQUALIZE_PORT to change it (install_pi.sh picks 8080
if Spotipi Photo's panel already has 80 on the same Pi).
"""

import io
import os
import socket
import subprocess
import sys
import time

from PIL import Image

sys.dont_write_bytecode = True      # runs as root; keep __pycache__ out

from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, url_for

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from display_logic import panel_config_paths, panel_geometry, read_panel_config, spotipi_root  # noqa: E402
from render import THEMES, album_palette, auto_bars, colour_field, peak_colour_for, theme_css  # noqa: E402
from styles import STYLE_GROUPS, STYLE_LABELS, STYLES, draw, sample_levels  # noqa: E402
from state import COVER_PATH, PREVIEW_PATH, read_state, read_status, reset_timer, write_state  # noqa: E402

app = Flask(__name__)

VALID_MODES = {"on", "spotify", "always", "off"}
VALID_SOURCES = {"airplay", "demo"}
BAR_CHOICES = [0, 4, 8, 16, 32, 64]
THEME_LABELS = {"vapor": "Vapor", "classic": "Classic", "rainbow": "Rainbow",
                "ice": "Ice", "sunset": "Sunset", "fire": "Fire", "ocean": "Ocean",
                "forest": "Forest", "aurora": "Aurora", "amber": "Amber",
                "mono": "Warm white", "pastel": "Pastel", "thermal": "Thermal", "teal": "Teal", "phosphor": "Phosphor",
                "album": "Album cover"}
VALID_SHARE = {"auto", "equalize", "spotipi"}
CONFIG_INI = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config", "rgb_options.ini"))
PANEL_SWITCH = "/usr/local/bin/equalize-panel"
SPOTIPI_UNIT = os.environ.get("SPOTIPI_UNIT_FILE", "/etc/systemd/system/spotipi.service")


def panel_size():
    """(width, height) of the LED panel, from rgb_options.ini."""
    try:
        w, h, _ = panel_geometry(read_panel_config(
            panel_config_paths(os.path.dirname(CONFIG_INI), spotipi_root(SPOTIPI_UNIT))))
        return w, h
    except Exception:
        return 64, 64


def _active(unit):
    try:
        return subprocess.run(["systemctl", "is-active", "--quiet", unit], timeout=3).returncode == 0
    except Exception:
        return False


def share_info():
    """Is Spotipi Photo on this Pi too, and which of the two has the panel?"""
    if not os.path.exists(SPOTIPI_UNIT):
        return {"installed": False}
    owner = "equalize" if _active("equalize") else "spotipi" if _active("spotipi") else None
    return {"installed": True, "owner": owner, "mode": read_state().get("panel_share", "auto"),
            "url": "http://%s.local/" % socket.gethostname()}


# Settings both programs have, each its own copy. Different values mean the
# panel changes when it's handed over: brighter, or lit in the other's quiet hours.
SHARED_SETTINGS = [
    ("brightness", "Brightness"),
    ("dimmer_enabled", "Dim after sunset"),
    ("dim_brightness", "Night brightness"),
    ("latitude", "Latitude"),
    ("longitude", "Longitude"),
    ("schedule_enabled", "Quiet hours"),
    ("schedule_off", "Quiet hours from"),
    ("schedule_on", "Quiet hours until"),
    ("timer_enabled", "Screen timer"),
    ("timer_minutes", "Screen timer minutes"),
]
# Panel settings that must match, or the panel flickers or draws wrongly
# when the other program takes over.
PANEL_KEYS = ["rows", "columns", "chain_length", "parallel", "hardware_mapping",
              "gpio_slowdown", "rotate", "pwm_bits", "pwm_lsb_nanoseconds", "led_rgb_sequence",
              "scan_mode", "row_address_type", "multiplexing", "refresh_rate"]


def _spotipi_state(root):
    import json as _json
    try:
        with open(os.path.join(root, "config", "state.json")) as f:
            return _json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _shown(v):
    return "on" if v is True else "off" if v is False else str(v)


def differences():
    """Where Equalize's settings and Spotipi Photo's differ: [(what, here, there)]."""
    root = spotipi_root(SPOTIPI_UNIT)
    if not root:
        return []
    here, there = read_state(), _spotipi_state(root)
    out = []
    for key, label in SHARED_SETTINGS:
        if key in there and here.get(key) != there[key]:
            out.append((label, _shown(here.get(key)), _shown(there[key])))
    mine = read_panel_config(panel_config_paths(os.path.dirname(CONFIG_INI), root))
    theirs = read_panel_config([os.path.join(root, "config", "rgb_options.ini"),
                                os.path.join(root, "config", "rgb_options.local.ini")])
    for key in PANEL_KEYS:
        a, b = mine.get(key), theirs.get(key)
        if a is not None and b is not None and a.strip() != b.strip():   # not set = the driver's default
            out.append(("Panel setting %s" % key, a, b))
    return out


def _int(name, default, lo, hi):
    try:
        return max(lo, min(hi, int(request.form.get(name, default))))
    except (TypeError, ValueError):
        return default


def pi_temp_c():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except (FileNotFoundError, ValueError, OSError):
        return None


def uptime_seconds():
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except (FileNotFoundError, ValueError, OSError):
        return None


def dashboard():
    st = read_status()
    s = read_state()
    remaining = None
    if s.get("timer_enabled") and s.get("timer_started"):
        remaining = max(0, int(s["timer_minutes"] * 60 - (time.time() - s["timer_started"])))
    return {
        "status": st,
        "alive": bool(st) and st.get("age_s", 999) <= 15,
        "pi_temp_c": pi_temp_c(),
        "uptime_s": uptime_seconds(),
        "timer_remaining_s": remaining,
        "share": share_info(),
    }


def done():
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(ok=True)
    return redirect(url_for("index"))


@app.route("/")
def index():
    # Album cover first: the default
    themes = [(t, THEME_LABELS.get(t, t.title()), theme_css(t))
              for t in sorted(THEMES, key=lambda t: t != "album")]
    style_groups = [(g, [(st, STYLE_LABELS[st]) for st in members]) for g, members in STYLE_GROUPS]
    w, h = panel_size()
    return render_template("index.html", s=read_state(), dash=dashboard(),
                           themes=themes, theme_names=THEME_LABELS, diffs=differences(), style_groups=style_groups, bar_choices=BAR_CHOICES,
                           panel_aspect="%d / %d" % (w, h), ui_skins=UI_SKINS, logos=LOGOS)


@app.route("/style/<name>.png")
def style_preview(name):
    """A still of one style, at the real panel size, in the current colours."""
    if name not in STYLES:
        return Response(status=404)
    state = read_state()
    w, h = panel_size()
    n = int(state.get("bars") or 0) or auto_bars(w)
    theme = state.get("theme", "album")
    theme = theme if theme in THEMES else "album"
    palette = None
    if theme == "album":
        # the cover of the last song played, as the display program saved it
        try:
            with Image.open(COVER_PATH) as art:
                palette = album_palette(art.convert("RGB"), n)
        except (OSError, ValueError):
            palette = None
        if palette is None:
            theme = "mono"                     # what the panel shows with no cover
    levels, peaks = sample_levels(n)
    img = draw(name, levels, peaks, w, h, colour_field(theme, n, h, palette), peak_colour_for(theme),
               still=True, dance_lanes=int(state.get("dance_lanes", 4)))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return Response(buf.getvalue(), mimetype="image/png", headers={"Cache-Control": "no-store"})


@app.route("/preview.png")
def preview():
    if os.path.exists(PREVIEW_PATH):
        resp = send_file(PREVIEW_PATH, mimetype="image/png")
        resp.headers["Cache-Control"] = "no-store"
        return resp
    px = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
          b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00"
          b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82")
    return Response(px, mimetype="image/png")


@app.route("/mode", methods=["POST"])
def set_mode():
    mode = request.form.get("mode", "on")
    state = read_state()
    state["mode"] = mode if mode in VALID_MODES else "on"
    reset_timer(state)               # a deliberate mode change restarts the sleep timer
    write_state(state)
    return done()


@app.route("/brightness", methods=["POST"])
def set_brightness():
    state = read_state()
    state["brightness"] = _int("brightness", 60, 1, 100)
    write_state(state)
    return done()


@app.route("/share/match", methods=["POST"])
def match_spotipi():
    """Copy Spotipi Photo's brightness, night dimming, quiet hours and timer
    here, so the panel behaves the same whichever program has it."""
    root = spotipi_root(SPOTIPI_UNIT)
    if root:
        there = _spotipi_state(root)
        state = read_state()
        for key, _ in SHARED_SETTINGS + [("timer_started", "")]:
            if key in there:
                state[key] = there[key]
        write_state(state)
    return done()


@app.route("/look", methods=["POST"])
def set_look():
    state = read_state()
    style = request.form.get("style", "ledring")
    state["style"] = style if style in STYLES else "ledring"
    theme = request.form.get("theme", "album")
    state["theme"] = theme if theme in THEMES else "album"
    bars = _int("bars", 0, 0, 128)
    state["bars"] = bars if bars in BAR_CHOICES else 0
    state["peaks"] = request.form.get("peaks") == "on"
    state["sensitivity"] = _int("sensitivity", 50, 1, 100)
    state["dance_lanes"] = 8 if request.form.get("dance_lanes") == "8" else 4
    song = request.form.get("song_text", "off")
    state["song_text"] = song if song in ("off", "change", "always") else "off"
    size = request.form.get("song_size", "medium")
    state["song_size"] = size if size in ("small", "medium", "large") else "medium"
    write_state(state)
    return done()


# The control panel's skins, in the order the switch shows them. Rack first: the default.
# ------------------------------------------------- Spotify Connect speakers
# OwnTone (the Spotify Connect route) runs on this Pi; its speaker list is
# offered here so you choose where Spotify plays without a second app.
OWNTONE = os.environ.get("EQUALIZE_OWNTONE", "http://127.0.0.1:3689")


def _owntone(path, body=None, method=None):
    import json as _json
    import urllib.request
    req = urllib.request.Request(OWNTONE + path, method=method,
                                 data=None if body is None else _json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as r:
        raw = r.read()
    return _json.loads(raw) if raw else {}


@app.route("/spotify/speakers")
def spotify_speakers():
    """The speakers Spotify can play to. The panel's own copy (OwnTone's
    pipe output) is always on, so it isn't offered."""
    try:
        outs = _owntone("/api/outputs").get("outputs", [])
    except Exception:
        return jsonify(ok=False, speakers=[])
    return jsonify(ok=True, speakers=[{"id": o["id"], "name": o["name"], "selected": bool(o.get("selected"))}
                                      for o in outs if o.get("type") != "fifo"])


@app.route("/spotify/speakers", methods=["POST"])
def set_spotify_speakers():
    try:
        outs = _owntone("/api/outputs").get("outputs", [])
        known = {o["id"] for o in outs}
        chosen = [i for i in request.form.getlist("speaker") if i in known]
        panel = [o["id"] for o in outs if o.get("type") == "fifo"]
        _owntone("/api/outputs/set", {"outputs": chosen + panel}, "PUT")
    except Exception:
        return Response("OwnTone isn't answering", status=502)
    return done()


UI_SKINS = {"rack": "Rack", "player": "Player", "silver": "Silver"}

# The logos, made by image/build_logos.py. First = default.
LOGOS = {"ledring": "LED ring", "ring": "Ring", "led": "LED grid"}
LOGO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "image", "logos"))


def chosen_logo():
    key = read_state().get("logo")
    return key if key in LOGOS else next(iter(LOGOS))


def logo_file(key, name, mimetype=None):
    """image/logos/<key>/<name>; key is always one of LOGOS, never typed in."""
    path = os.path.join(LOGO_DIR, key, name)
    if key not in LOGOS or not os.path.exists(path):
        return Response(status=404)
    resp = send_file(path, mimetype=mimetype)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/favicon.ico")
def favicon():
    return logo_file(chosen_logo(), "favicon.ico", "image/x-icon")


@app.route("/icon.svg")
def icon_svg():
    return logo_file(chosen_logo(), "icon.svg", "image/svg+xml")


@app.route("/apple-touch-icon.png")
def apple_icon():
    return logo_file(chosen_logo(), "icon-180.png")


@app.route("/icon-<int:px>.png")
def icon_png(px):
    if px not in (16, 32, 64, 192, 512):
        return Response(status=404)
    return logo_file(chosen_logo(), "icon-%d.png" % px)


@app.route("/logo/<key>.png")
def logo_preview(key):
    return logo_file(key, "icon-192.png")


@app.route("/manifest.webmanifest")
def manifest():
    v = chosen_logo()
    return jsonify(name="Equalize", short_name="Equalize", start_url="/", display="standalone",
                   background_color="#0f1012", theme_color="#0f1012",
                   icons=[{"src": "/icon-192.png?v=" + v, "sizes": "192x192", "type": "image/png"},
                          {"src": "/icon-512.png?v=" + v, "sizes": "512x512", "type": "image/png"}])


@app.route("/logo", methods=["POST"])
def set_logo():
    state = read_state()
    key = request.form.get("logo", "")
    state["logo"] = key if key in LOGOS else next(iter(LOGOS))
    write_state(state)
    return done()


@app.route("/ui", methods=["POST"])
def set_ui():
    """Which skin the control panel wears. The LED panel is unaffected."""
    state = read_state()
    skin = request.form.get("ui", "rack")
    state["ui"] = skin if skin in UI_SKINS else "rack"
    write_state(state)
    return done()


@app.route("/source", methods=["POST"])
def set_source():
    src = request.form.get("audio_source", "airplay")
    state = read_state()
    state["audio_source"] = src if src in VALID_SOURCES else "airplay"
    write_state(state)
    return done()


@app.route("/share", methods=["POST"])
def set_share():
    """Who drives the LED panel when Spotipi Photo is on the same Pi."""
    mode = request.form.get("panel_share", "auto")
    state = read_state()
    state["panel_share"] = mode if mode in VALID_SHARE else "auto"
    write_state(state)
    if os.path.exists(PANEL_SWITCH):
        subprocess.run([PANEL_SWITCH, "use", state["panel_share"]], timeout=30)
    return done()


@app.route("/dimmer", methods=["POST"])
def set_dimmer():
    state = read_state()
    state["dimmer_enabled"] = request.form.get("dimmer_enabled") == "on"
    state["dim_brightness"] = _int("dim_brightness", 20, 1, 100)
    for key, lim in (("latitude", 90.0), ("longitude", 180.0)):
        try:
            state[key] = max(-lim, min(lim, float(request.form.get(key))))
        except (TypeError, ValueError):
            pass
    write_state(state)
    return done()


@app.route("/timer", methods=["POST"])
def set_timer():
    state = read_state()
    state["timer_enabled"] = request.form.get("timer_enabled") == "on"
    state["timer_minutes"] = _int("timer_minutes", 30, 1, 1440)
    reset_timer(state)
    write_state(state)
    return done()


@app.route("/schedule", methods=["POST"])
def set_schedule():
    state = read_state()
    state["schedule_enabled"] = request.form.get("schedule_enabled") == "on"
    state["schedule_off"] = request.form.get("schedule_off", "23:00")
    state["schedule_on"] = request.form.get("schedule_on", "07:00")
    write_state(state)
    return done()


@app.route("/status")
def status():
    d = dashboard()
    d["state"] = read_state()
    return jsonify(d)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("EQUALIZE_PORT", "80")))
