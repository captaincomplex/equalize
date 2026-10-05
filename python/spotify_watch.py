#!/usr/bin/env python3
"""
spotify_watch.py -- hands the LED panel over when Spotify Connect plays.

AirPlay tells Equalize when music starts and stops (shairport-sync runs
equalize-panel). Spotify Connect goes through OwnTone, which has no such
hook, so this asks OwnTone every two seconds whether it's playing:

    starts playing          ->  equalize-panel airplay-start  (Equalize takes the panel)
    stopped for 10 seconds  ->  equalize-panel airplay-stop   (Spotipi Photo gets it back)

The same 10 seconds as AirPlay, so skipping a track doesn't flick the panel.
Only matters when Spotipi Photo shares the Pi; harmless otherwise.

    python3 spotify_watch.py [--api http://127.0.0.1:3689] [--every 2] [--hold 10]

Standard library only.
"""
import argparse
import json
import subprocess
import time
import urllib.request


def playing(api):
    """True/False from OwnTone, or None if OwnTone isn't answering."""
    try:
        with urllib.request.urlopen(api + "/api/player", timeout=3) as r:
            return json.load(r).get("state") == "play"
    except (OSError, ValueError):
        return None


class Watch:
    """Turns a stream of 'is it playing?' answers into start/stop actions."""

    def __init__(self, hold_s=10.0):
        self.hold_s = hold_s
        self.showing = False
        self.quiet_since = None

    def step(self, is_playing, now):
        if is_playing:
            self.quiet_since = None
            if not self.showing:
                self.showing = True
                return "airplay-start"
        elif self.showing:
            if self.quiet_since is None:
                self.quiet_since = now
            elif now - self.quiet_since >= self.hold_s:
                self.showing = False
                self.quiet_since = None
                return "airplay-stop"
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:3689")
    ap.add_argument("--every", type=float, default=2.0)
    ap.add_argument("--hold", type=float, default=10.0)
    ap.add_argument("--panel", default="/usr/local/bin/equalize-panel")
    a = ap.parse_args()
    w = Watch(a.hold)
    while True:
        p = playing(a.api)
        action = w.step(bool(p), time.monotonic()) if p is not None else None
        if action:
            subprocess.run([a.panel, action], check=False)
        time.sleep(a.every)


if __name__ == "__main__":
    main()
