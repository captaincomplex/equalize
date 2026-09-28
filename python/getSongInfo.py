"""
getSongInfo.py -- minimal Spotify "now playing" helper (from Spotipi Photo).

Reuses the cached token created by generate-token.sh (the .cache-<username>
file). The same token file as Spotipi Photo works here: the scope is identical.

    info = getSongInfo(username, token_path)
    info = { "is_playing": bool, "image_url": str|None,
             "name": str|None, "artist": str|None }
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Must match SCOPE in generateToken.py.
SCOPE = "user-read-currently-playing"

_clients = {}


def _client(username, token_path):
    key = (username, token_path)
    if key not in _clients:
        auth = SpotifyOAuth(
            scope=SCOPE,
            username=username,
            cache_path=token_path,
            open_browser=False,
        )
        _clients[key] = spotipy.Spotify(auth_manager=auth, requests_timeout=5)
    return _clients[key]


def getSongInfo(username, token_path):
    result = {"is_playing": False, "image_url": None, "name": None, "artist": None}
    try:
        sp = _client(username, token_path)
        playback = sp.currently_playing()
        if not playback or not playback.get("item"):
            return result
        item = playback["item"]
        images = item.get("album", {}).get("images", [])
        result["name"] = item.get("name")
        artists = item.get("artists", [])
        if artists:
            result["artist"] = ", ".join(a.get("name", "") for a in artists if a.get("name"))
        if images:
            result["image_url"] = images[-1]["url"]      # smallest; the panel is tiny
        result["is_playing"] = bool(playback.get("is_playing"))
    except Exception:
        # token expired / no network / podcast -> treat as not playing
        return result
    return result
