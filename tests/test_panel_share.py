"""Tests for config/equalize-panel, the switch that hands the LED panel between
Equalize and Spotipi Photo. systemctl is replaced by a stand-in that records
what it was asked to do. Run: python3 -m pytest"""

import json
import os
import subprocess

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "config", "equalize-panel")


@pytest.fixture
def pi(tmp_path):
    """A pretend Pi: a state file, a stand-in systemctl, a Spotipi unit file."""
    log = tmp_path / "systemctl.log"
    fake = tmp_path / "systemctl"
    fake.write_text('#!/bin/bash\necho "$*" >> "%s"\n'
                    '[ "$1" = is-active ] && exit 1\nexit 0\n' % log)
    fake.chmod(0o755)
    unit = tmp_path / "spotipi.service"
    unit.write_text("[Unit]\n")
    state = tmp_path / "state.json"

    def run(*args, mode=None, spotipi=True, display=None):
        st = {}
        if mode:
            st["panel_share"] = mode
        if display:
            st["mode"] = display
        state.write_text(json.dumps(st))
        if log.exists():
            log.unlink()
        env = dict(os.environ, SYSTEMCTL=str(fake), EQUALIZE_STATE=str(state),
                   SPOTIPI_UNIT_FILE=str(unit if spotipi else tmp_path / "absent"),
                   EQUALIZE_PANEL_LOCK=str(tmp_path / "lock"))
        subprocess.run(["bash", SCRIPT, *args], env=env, check=True)
        return log.read_text().split("\n")[:-1] if log.exists() else []

    return run


def test_airplay_start_hands_panel_to_equalize_in_auto(pi):
    assert pi("airplay-start") == ["stop spotipi.service", "start equalize.service"]


def test_airplay_stop_hands_panel_back_in_auto(pi):
    assert pi("airplay-stop") == ["stop equalize.service", "start spotipi.service"]


@pytest.mark.parametrize("mode", ["equalize", "spotipi"])
def test_airplay_hooks_do_nothing_when_pinned(pi, mode):
    assert pi("airplay-start", mode=mode) == []
    assert pi("airplay-stop", mode=mode) == []


def test_other_one_is_always_stopped_first(pi):
    calls = pi("use", "equalize")
    assert calls.index("stop spotipi.service") < calls.index("start equalize.service")


def test_boot_gives_panel_to_spotipi_unless_pinned_to_equalize(pi):
    assert pi("boot")[-1] == "start spotipi.service"
    assert pi("boot", mode="equalize")[-1] == "start equalize.service"


def test_without_spotipi_equalize_always_has_the_panel(pi):
    assert pi("boot", spotipi=False) == ["start equalize.service"]
    assert pi("airplay-stop", spotipi=False) == []


def test_use_auto_leaves_the_panel_alone(pi):
    assert pi("use", "auto") == []


def test_equalize_set_to_off_leaves_the_panel_with_spotipi(pi):
    # taking the panel only to show nothing would blank the photos
    assert pi("airplay-start", display="off") == []
    assert pi("airplay-start", display="on") == ["stop spotipi.service", "start equalize.service"]


def test_equalize_hands_back_after_a_minute_without_music():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
    from display_logic import should_hand_back
    auto = {"panel_share": "auto", "audio_source": "airplay"}
    assert should_hand_back(auto, True, silent_s=61, running_s=300)
    assert not should_hand_back(auto, True, silent_s=30, running_s=300)          # a pause between songs
    assert not should_hand_back(auto, True, silent_s=61, running_s=20)           # just started
    assert not should_hand_back(auto, False, silent_s=600, running_s=600)        # no Spotipi Photo
    assert not should_hand_back(dict(auto, panel_share="equalize"), True, 600, 600)   # pinned
    assert not should_hand_back(dict(auto, audio_source="demo"), True, 600, 600)


def test_every_decision_is_explained(pi, tmp_path):
    # logger is replaced by a stand-in, so the explanation can be read back
    logged = tmp_path / "logger.log"
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "logger").write_text('#!/bin/bash\necho "$*" >> "%s"\n' % logged)
    (fake / "logger").chmod(0o755)
    os.environ["PATH"] = "%s:%s" % (fake, os.environ["PATH"])
    try:
        pi("airplay-stop", mode="equalize")
        pi("airplay-start", display="off")
    finally:
        os.environ["PATH"] = os.environ["PATH"].split(":", 1)[1]
    text = logged.read_text()
    assert "no change (Sharing is set to equalize)" in text
    assert "Equalize's display is Off" in text
