"""The Spotify Connect watcher: hands the panel over on play, back after 10 s quiet."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from spotify_watch import Watch  # noqa: E402


def test_play_then_stop_after_ten_quiet_seconds():
    w = Watch(hold_s=10)
    assert w.step(False, 0) is None                 # nothing playing, nothing to do
    assert w.step(True, 1) == "airplay-start"
    assert w.step(True, 3) is None                  # still playing: no repeats
    assert w.step(False, 5) is None                 # paused...
    assert w.step(False, 12) is None                # ...7 s isn't enough
    assert w.step(False, 15) == "airplay-stop"      # 10 s quiet: hand back
    assert w.step(False, 30) is None


def test_skipping_a_track_does_not_flick_the_panel():
    w = Watch(hold_s=10)
    w.step(True, 0)
    assert w.step(False, 2) is None                 # gap between tracks
    assert w.step(True, 4) is None                  # music again: stays put
    assert w.step(False, 6) is None
    assert w.step(False, 15) is None                # the 10 s count restarted at 6
    assert w.step(False, 16) == "airplay-stop"
