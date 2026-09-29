"""Tests for when the bars show. Run: python3 -m pytest"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from display_logic import (compute_effective, effective_brightness,  # noqa: E402
                           in_quiet_hours, timer_expired)

NOON = datetime(2026, 6, 21, 12, 0)


def test_auto_mode_follows_the_music():
    s = {"mode": "on"}
    assert compute_effective(s, True, False, now=NOON) == "bars"
    assert compute_effective(s, False, True, now=NOON) == "off"


def test_spotify_mode_needs_both_sound_and_spotify():
    s = {"mode": "spotify"}
    assert compute_effective(s, True, True, now=NOON) == "bars"
    assert compute_effective(s, True, False, now=NOON) == "off"    # e.g. Apple Music
    assert compute_effective(s, False, True, now=NOON) == "off"    # Spotify on another device


def test_always_and_off():
    assert compute_effective({"mode": "always"}, False, False, now=NOON) == "bars"
    assert compute_effective({"mode": "off"}, True, True, now=NOON) == "off"


def test_quiet_hours_beat_music():
    s = {"mode": "on", "schedule_enabled": True, "schedule_off": "23:00", "schedule_on": "07:00"}
    assert compute_effective(s, True, True, now=datetime(2026, 1, 1, 23, 30)) == "off"
    assert compute_effective(s, True, True, now=datetime(2026, 1, 1, 12, 0)) == "bars"


def test_quiet_hours_across_midnight():
    assert in_quiet_hours(datetime(2026, 1, 1, 2, 0), "23:00", "07:00")
    assert not in_quiet_hours(datetime(2026, 1, 1, 8, 0), "23:00", "07:00")


def test_sleep_timer():
    s = {"timer_enabled": True, "timer_minutes": 30, "timer_started": 1000}
    assert not timer_expired(s, now_epoch=1000 + 29 * 60)
    assert timer_expired(s, now_epoch=1000 + 30 * 60)


def test_dimmer_at_night_in_london():
    s = {"brightness": 80, "dim_brightness": 10, "dimmer_enabled": True,
         "latitude": 51.5, "longitude": -0.13}
    assert effective_brightness(s, datetime(2026, 12, 21, 23, 0)) == 10
    assert effective_brightness(s, datetime(2026, 6, 21, 13, 0)) == 80
