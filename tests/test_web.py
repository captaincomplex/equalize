"""The control panel: its two skins, and that the page renders in each."""

import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "python"))
sys.path.insert(0, os.path.join(ROOT, "python", "client"))

import state  # noqa: E402


def client(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "STATE_PATH", str(tmp_path / "state.json"))
    import app as webapp
    monkeypatch.setattr(webapp, "read_state", state.read_state)
    monkeypatch.setattr(webapp, "write_state", state.write_state)
    return webapp.app.test_client()


def test_rack_is_the_default_skin(monkeypatch, tmp_path):
    page = client(monkeypatch, tmp_path).get("/").get_data(as_text=True)
    assert 'data-ui="rack"' in page
    assert 'name="ui" value="rack" checked' in page


def test_switching_to_player_and_back(monkeypatch, tmp_path):
    c = client(monkeypatch, tmp_path)
    assert c.post("/ui", data={"ui": "player"}).status_code == 302
    assert state.read_state()["ui"] == "player"
    assert 'data-ui="player"' in c.get("/").get_data(as_text=True)
    c.post("/ui", data={"ui": "winamp-but-made-up"})
    assert state.read_state()["ui"] == "rack"          # unknown names fall back


def test_every_setting_is_still_on_the_page(monkeypatch, tmp_path):
    page = client(monkeypatch, tmp_path).get("/").get_data(as_text=True)
    for field in ("mode", "brightness", "style", "theme", "bars", "sensitivity", "peaks",
                  "audio_source", "timer_enabled", "timer_minutes", "schedule_enabled",
                  "schedule_off", "schedule_on", "dimmer_enabled", "dim_brightness",
                  "latitude", "longitude"):
        assert 'name="%s"' % field in page, field
    assert "fonts/barlow-400.woff2" in page             # served by the Pi, no internet needed
