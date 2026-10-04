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
import subprocess
import sys
import time

sys.dont_write_bytecode = True      # runs as root; keep __pycache__ out

from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, url_for

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from display_logic import panel_config_paths, panel_geometry, read_panel_config  # noqa: E402
from render import THEMES, auto_bars, colour_field, peak_colour_for, theme_css  # noqa: E402
from styles import STYLE_LABELS, STYLES, draw, sample_levels  # noqa: E402
from state import PREVIEW_PATH, read_state, read_status, reset_timer, write_state  # noqa: E402

app = Flask(__name__)

VALID_MODES = {"on", "spotify", "always", "off"}
VALID_SOURCES = {"airplay", "demo"}
BAR_CHOICES = [0, 8, 16, 32, 64]
THEME_LABELS = {"vapor": "Vapor", "classic": "Classic", "rainbow": "Rainbow",
                "ice": "Ice", "sunset": "Sunset", "fire": "Fire", "ocean": "Ocean",
                "forest": "Forest", "aurora": "Aurora", "amber": "Amber",
                "mono": "Warm white", "pastel": "Pastel", "thermal": "Thermal",
                "album": "Album cover"}
VALID_SHARE = {"auto", "equalize", "spotipi"}
CONFIG_INI = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config", "rgb_options.ini"))
PANEL_SWITCH = "/usr/local/bin/equalize-panel"
SPOTIPI_UNIT = os.environ.get("SPOTIPI_UNIT_FILE", "/etc/systemd/system/spotipi.service")


def panel_size():
    """(width, height) of the LED panel, from rgb_options.ini."""
    try:
        w, h, _ = panel_geometry(read_panel_config(panel_config_paths(os.path.dirname(CONFIG_INI))))
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
    return {"installed": True, "owner": owner, "mode": read_state().get("panel_share", "auto")}


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
    themes = [(t, THEME_LABELS.get(t, t.title()), theme_css(t)) for t in THEMES]
    styles = [(st, STYLE_LABELS[st]) for st in STYLES]
    w, h = panel_size()
    return render_template("index.html", s=read_state(), dash=dashboard(),
                           themes=themes, styles=styles, bar_choices=BAR_CHOICES,
                           panel_aspect="%d / %d" % (w, h), ui_skins=UI_SKINS)


@app.route("/style/<name>.png")
def style_preview(name):
    """A still of one style, at the real panel size, in the current colours."""
    if name not in STYLES:
        return Response(status=404)
    state = read_state()
    w, h = panel_size()
    n = int(state.get("bars") or 0) or auto_bars(w)
    theme = state.get("theme", "vapor")
    theme = "rainbow" if theme == "album" else theme if theme in THEMES else "vapor"
    levels, peaks = sample_levels(n)
    img = draw(name, levels, peaks, w, h, colour_field(theme, n, h), peak_colour_for(theme),
               still=True)
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


@app.route("/look", methods=["POST"])
def set_look():
    state = read_state()
    style = request.form.get("style", "sunset")
    state["style"] = style if style in STYLES else "sunset"
    theme = request.form.get("theme", "vapor")
    state["theme"] = theme if theme in THEMES else "vapor"
    bars = _int("bars", 0, 0, 128)
    state["bars"] = bars if bars in BAR_CHOICES else 0
    state["peaks"] = request.form.get("peaks") == "on"
    state["sensitivity"] = _int("sensitivity", 50, 1, 100)
    write_state(state)
    return done()


# The control panel's skins, in the order the switch shows them. Rack first: the default.
UI_SKINS = {"rack": "Rack", "player": "Player", "daylight": "Daylight", "silver": "Silver"}


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
