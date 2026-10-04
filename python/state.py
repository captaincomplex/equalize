"""
state.py -- shared, atomic read/write of the live settings and status.

config/state.json   settings, written by the web panel, read by the display
                    daemon twice a second, so changes apply with no restart.
status.json         what the daemon is doing right now (for the dashboard).
current.png         a snapshot of the panel (for the dashboard preview).

status.json and current.png change several times a second, so they live in
/dev/shm -- a folder held in memory -- rather than on the SD card, which wears
out with constant rewriting.
"""

import json
import os
import tempfile
import time

DIR = os.path.dirname(__file__)
STATE_PATH = os.path.abspath(os.path.join(DIR, "..", "config", "state.json"))

RUNTIME_DIR = "/dev/shm/equalize" if os.path.isdir("/dev/shm") else \
    os.path.abspath(os.path.join(DIR, "..", "config"))
STATUS_PATH = os.path.join(RUNTIME_DIR, "status.json")
PREVIEW_PATH = os.path.join(RUNTIME_DIR, "current.png")

DEFAULT_STATE = {
    # "on"      -- bars while music is arriving over AirPlay, from any app
    # "spotify" -- as "on", but only while Spotify says your account is playing
    # "always"  -- bars all the time (a faint floor row when silent)
    # "off"     -- dark
    "mode": "on",
    "brightness": 60,               # 1-100, the daytime level

    # Look
    "style": "sunset",              # see styles.STYLES
    "theme": "vapor",               # see render.THEMES
    "bars": 0,                      # 0 = automatic for the panel width
    "peaks": True,                  # the little falling caps above the bars
    "sensitivity": 50,              # 1-100; higher = taller, busier bars

    # How the control panel itself looks: "rack" (studio rack units) or
    # "player" (an early-2000s media player). The LED panel is unaffected.
    "ui": "rack",

    # Sound
    "audio_source": "airplay",      # "airplay" or "demo"

    # Only matters when Spotipi Photo is installed on the same Pi (they can't
    # both drive the panel). "auto": Equalize while AirPlay music plays,
    # Spotipi Photo the rest of the time. "equalize" / "spotipi": always that one.
    "panel_share": "auto",

    # Sunrise/sunset dimmer
    "dimmer_enabled": False,
    "dim_brightness": 20,
    "latitude": 51.5074,            # default: London
    "longitude": -0.1278,

    # Sleep timer
    "timer_enabled": False,
    "timer_minutes": 30,
    "timer_started": 0,

    # Recurring daily quiet hours
    "schedule_enabled": False,
    "schedule_off": "23:00",
    "schedule_on": "07:00",
}


def _atomic_write(path, data, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=indent)
        os.replace(tmp, path)          # atomic on POSIX: readers never see half a file
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def read_state():
    """Return the current settings, filling in any missing defaults."""
    try:
        with open(STATE_PATH, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError):
        data = {}
    merged = dict(DEFAULT_STATE)
    merged.update(data or {})
    return merged


def write_state(state):
    _atomic_write(STATE_PATH, state, indent=2)


def reset_timer(state):
    """Mark the sleep timer as starting now."""
    state["timer_started"] = int(time.time())
    return state


def write_status(status):
    _atomic_write(STATUS_PATH, status)


def read_status():
    """The daemon's status dict plus "age_s" (seconds since written), or {}."""
    try:
        with open(STATUS_PATH, "r") as f:
            data = json.load(f) or {}
        data["age_s"] = max(0, int(time.time() - os.path.getmtime(STATUS_PATH)))
        return data
    except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError):
        return {}
