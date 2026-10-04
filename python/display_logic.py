"""
display_logic.py -- pure decision logic for whether the bars should show.

Kept free of any hardware imports so it can be unit-tested on any machine
(see tests/test_logic.py). Adapted from Spotipi Photo; the quiet-hours,
sleep-timer and sunrise/sunset code is unchanged.
"""

import math
import time
from datetime import datetime


def parse_hhmm(s):
    """'23:00' -> (23, 0). Returns None on bad input."""
    try:
        h, m = s.split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return h, m
    except Exception:
        pass
    return None


def in_quiet_hours(now, off_str, on_str):
    """True if `now` (a datetime) falls within the off..on window.
    Handles windows that cross midnight (e.g. 23:00 -> 07:00)."""
    off = parse_hhmm(off_str)
    on = parse_hhmm(on_str)
    if not off or not on or off == on:
        return False
    minutes = now.hour * 60 + now.minute
    off_m = off[0] * 60 + off[1]
    on_m = on[0] * 60 + on[1]
    if off_m < on_m:
        return off_m <= minutes < on_m
    return minutes >= off_m or minutes < on_m


def timer_expired(state, now_epoch=None):
    """True if the sleep timer is enabled and has elapsed."""
    if not state.get("timer_enabled"):
        return False
    started = state.get("timer_started", 0) or 0
    if started <= 0:
        return False
    if now_epoch is None:
        now_epoch = time.time()
    minutes = max(0, int(state.get("timer_minutes", 30)))
    return (now_epoch - started) >= minutes * 60


def sun_times(date, lat, lon):
    """Sunrise and sunset for a calendar date and location, as naive local
    datetimes, or (None, None) for polar day/night. Standard sunrise equation
    (https://en.wikipedia.org/wiki/Sunrise_equation)."""
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return None, None
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None, None

    y, m, d = date.year, date.month, date.day
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
          + d + b - 1524.5)

    n = round(jd - 2451545.0 + 0.0008)
    j_star = n - lon / 360.0
    M = (357.5291 + 0.98560028 * j_star) % 360.0
    Mr = math.radians(M)
    C = (1.9148 * math.sin(Mr) + 0.0200 * math.sin(2 * Mr)
         + 0.0003 * math.sin(3 * Mr))
    lam = math.radians((M + C + 180.0 + 102.9372) % 360.0)
    j_transit = (2451545.0 + j_star + 0.0053 * math.sin(Mr)
                 - 0.0069 * math.sin(2 * lam))

    decl = math.asin(math.sin(lam) * math.sin(math.radians(23.44)))
    phi = math.radians(lat)
    cos_omega = ((math.sin(math.radians(-0.833)) - math.sin(phi) * math.sin(decl))
                 / (math.cos(phi) * math.cos(decl)))
    if cos_omega < -1 or cos_omega > 1:
        return None, None
    omega = math.degrees(math.acos(cos_omega))

    def _to_local(j):
        return datetime.fromtimestamp((j - 2440587.5) * 86400.0)

    return _to_local(j_transit - omega / 360.0), _to_local(j_transit + omega / 360.0)


def is_night(state, now=None):
    """True if the sunrise/sunset dimmer is on and it is currently night."""
    if not state.get("dimmer_enabled"):
        return False
    if now is None:
        now = datetime.now()
    rise, set_ = sun_times(now, state.get("latitude"), state.get("longitude"))
    if rise is None or set_ is None:
        return False
    return now < rise or now >= set_


def effective_brightness(state, now=None):
    """Brightness to apply right now (1-100): the dim level at night when the
    dimmer is on, otherwise the normal level."""
    day = int(state.get("brightness", 60))
    if is_night(state, now):
        return max(1, min(100, int(state.get("dim_brightness", 20))))
    return max(1, min(100, day))


def compute_effective(state, has_sound, spotify_playing, now=None, now_epoch=None):
    """Return what to render: 'off' or 'bars'.

    has_sound        music is arriving over AirPlay (or the demo is running)
    spotify_playing  Spotify reports your account is playing something

    Precedence:
      1. mode == 'off'          -> off
      2. quiet-hours schedule   -> off
      3. expired sleep timer    -> off
      4. mode == 'always'       -> bars, even when silent (a faint floor row)
      5. mode == 'spotify'      -> bars while music arrives AND Spotify is playing
      6. mode == 'on' (auto)    -> bars while music arrives, from any app
    """
    if now is None:
        now = datetime.now()
    mode = state.get("mode", "on")

    if mode == "off":
        return "off"
    if state.get("schedule_enabled") and in_quiet_hours(
        now, state.get("schedule_off", "23:00"), state.get("schedule_on", "07:00")
    ):
        return "off"
    if timer_expired(state, now_epoch):
        return "off"
    if mode == "always":
        return "bars"
    if mode == "spotify":
        return "bars" if (has_sound and spotify_playing) else "off"
    return "bars" if has_sound else "off"


# ---------------------------------------------------------------- panel shape
ROTATIONS = (0, 90, 180, 270)


def panel_geometry(d):
    """(width, height, rotate) of the picture, from rgb_options.ini's settings.

    The panels' own size is columns x chain_length wide and rows x parallel
    high. `rotate` turns the whole picture, so panels mounted on their side
    work: a 64x32 turned 90 degrees is 32 wide and 64 tall; two chained 64x64s
    (128x64) turned 90 degrees are 64 wide and 128 tall.
    """
    w = int(d["columns"]) * int(d.get("chain_length", 1))
    h = int(d["rows"]) * int(d.get("parallel", 1))
    try:
        rotate = int(d.get("rotate", 0))
    except ValueError:
        rotate = 0
    rotate = rotate if rotate in ROTATIONS else 0
    if rotate in (90, 270):
        w, h = h, w
    return w, h, rotate
