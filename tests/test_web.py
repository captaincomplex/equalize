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


def test_logo_choice_changes_the_icons(monkeypatch, tmp_path):
    c = client(monkeypatch, tmp_path)
    assert state.read_state()["logo"] == "ledring"                    # the default
    ledring = c.get("/icon-192.png").data
    assert c.post("/logo", data={"logo": "ring"}).status_code == 302
    assert state.read_state()["logo"] == "ring"
    assert c.get("/icon-192.png").data != ledring                     # the icon really changed
    for url in ("/favicon.ico", "/icon.svg", "/apple-touch-icon.png", "/manifest.webmanifest",
                "/logo/led.png"):
        assert c.get(url).status_code == 200, url
    assert c.get("/logo/../../etc.png").status_code == 404
    c.post("/logo", data={"logo": "nonsense"})
    assert state.read_state()["logo"] == "ledring"


def test_spotify_speakers_list_and_choice(monkeypatch, tmp_path):
    import app as webapp
    c = client(monkeypatch, tmp_path)
    sent = {}
    outputs = [{"id": "1", "name": "Living Room", "type": "AirPlay 2", "selected": False},
               {"id": "2", "name": "Equalize panel", "type": "fifo", "selected": True}]

    def fake(path, body=None, method=None):
        if method == "PUT":
            sent["body"] = body
            return {}
        return {"outputs": outputs}
    monkeypatch.setattr(webapp, "_owntone", fake)
    d = c.get("/spotify/speakers").get_json()
    assert d["ok"] and [s["name"] for s in d["speakers"]] == ["Living Room"]   # the pipe isn't offered
    assert c.post("/spotify/speakers", data={"speaker": ["1", "99"]}).status_code == 302
    assert sent["body"] == {"outputs": ["1", "2"]}          # unknown ids dropped, the panel's copy always on


def test_spotify_speakers_when_owntone_is_absent(monkeypatch, tmp_path):
    import app as webapp
    c = client(monkeypatch, tmp_path)

    def down(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(webapp, "_owntone", down)
    assert c.get("/spotify/speakers").get_json() == {"ok": False, "speakers": []}
    assert c.post("/spotify/speakers", data={"speaker": "1"}).status_code == 502
