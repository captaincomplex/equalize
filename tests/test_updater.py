"""The updater, against a pretend GitHub: a local repository with release
tags. Nothing is restarted: the steps after an update are stand-ins."""
import importlib
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "python"))


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A 'GitHub' with releases v1.0.0 and v1.1.0, and a Pi's copy on v1.0.0."""
    hub = tmp_path / "hub"
    hub.mkdir()
    sh(hub, "git", "init", "-q", "-b", "main")
    sh(hub, "git", "config", "user.email", "t@example.com")
    sh(hub, "git", "config", "user.name", "t")
    (hub / "config").mkdir()
    (hub / "program.py").write_text("v = 1\n")
    (hub / "config" / ".keep").write_text("")
    sh(hub, "git", "add", "-A")
    sh(hub, "git", "commit", "-q", "-m", "one")
    sh(hub, "git", "tag", "v1.0.0")
    pi = tmp_path / "pi"
    sh(tmp_path, "git", "clone", "-q", str(hub), str(pi))
    sh(pi, "git", "checkout", "-q", "v1.0.0")
    sh(pi, "git", "checkout", "-q", "-B", "main")
    (hub / "program.py").write_text("v = 2\n")
    sh(hub, "git", "commit", "-qam", "two")
    sh(hub, "git", "tag", "v1.1.0")
    (hub / "program.py").write_text("v = 3 (not released)\n")
    sh(hub, "git", "commit", "-qam", "three")

    import updater
    importlib.reload(updater)
    monkeypatch.setattr(updater, "ROOT", str(pi))
    monkeypatch.setattr(updater, "REPO_URL", str(hub))
    monkeypatch.setattr(updater, "STATUS_PATH", str(pi / "config" / "update.json"))
    monkeypatch.setattr(updater, "STATE_PATH", str(pi / "config" / "state.json"))
    monkeypatch.setattr(updater, "SERVICES", [])
    calls = []
    monkeypatch.setattr(updater, "after_update", lambda: calls.append("after") or True)
    return updater, hub, pi, calls


def test_finds_the_newest_release_not_the_newest_code(world):
    updater, hub, pi, _ = world
    st = updater.check()
    assert st["current"] == "v1.0.0" and st["latest"] == "v1.1.0" and st["available"] == "v1.1.0"


def test_updates_to_the_release_and_says_so(world):
    updater, hub, pi, calls = world
    assert updater.apply()
    assert (pi / "program.py").read_text() == "v = 2\n"          # the release, not "v = 3"
    st = updater.read_status()
    assert st["current"] == "v1.1.0" and not st["available"] and "Updated to v1.1.0" in st["last"]
    assert calls == ["after"]
    assert updater.check()["available"] is None                  # up to date now


def test_never_overwrites_a_file_changed_on_the_pi(world):
    updater, hub, pi, calls = world
    (pi / "program.py").write_text("my own edit\n")
    assert not updater.apply()
    assert (pi / "program.py").read_text() == "my own edit\n"
    assert "program.py" in updater.read_status()["error"] and calls == []


def test_settings_and_other_untracked_files_survive(world):
    updater, hub, pi, _ = world
    (pi / "config" / "state.json").write_text('{"theme": "teal"}')
    assert updater.apply()
    assert (pi / "config" / "state.json").read_text() == '{"theme": "teal"}'


def test_goes_back_if_the_new_version_does_not_start(world, monkeypatch):
    updater, hub, pi, calls = world
    monkeypatch.setattr(updater, "SERVICES", ["equalize-web"])
    monkeypatch.setattr(updater, "_active", lambda unit: True)
    monkeypatch.setattr(updater, "healthy", lambda units, **kw: len(calls) > 1)   # fails once
    assert not updater.apply()
    assert (pi / "program.py").read_text() == "v = 1\n"           # back on v1.0.0
    st = updater.read_status()
    assert "went back to v1.0.0" in st["error"] and st["current"] == "v1.0.0"


def test_a_copy_already_past_the_release_is_left_alone(world):
    updater, hub, pi, _ = world
    sh(pi, "git", "pull", "-q", str(hub), "main")                  # someone pulled the latest code
    assert updater.check()["available"] is None


def test_automatic_updates_default_on_and_can_be_turned_off(world):
    updater, hub, pi, _ = world
    assert updater.auto_updates_on()
    (pi / "config" / "state.json").write_text('{"auto_update": false}')
    assert not updater.auto_updates_on()


def test_a_display_handed_over_during_the_update_is_not_a_failure(world, monkeypatch):
    updater, hub, pi, _ = world
    monkeypatch.setattr(updater, "DISPLAYS", ["display"])
    state = {"display": "inactive", "web": "active"}

    class R:
        def __init__(self, code, out=""):
            self.returncode, self.stdout = code, out

    def fake_run(cmd, **kw):
        if cmd[1] == "is-active":
            return R(0 if state[cmd[-1]] == "active" else 3)
        if cmd[1] == "is-failed":
            return R(0 if state[cmd[-1]] == "failed" else 1)
        return R(0, "0")                                       # NRestarts
    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    monkeypatch.setattr(updater.time, "sleep", lambda s: None)
    assert updater.healthy(["web", "display"], wait_s=5, steady_s=0)       # handed over: fine
    state["display"] = "failed"
    assert not updater.healthy(["web", "display"], wait_s=0.2, steady_s=0)  # crashed: not
