#!/usr/bin/env python3
"""
generateToken.py -- do the one-off Spotify login and save the token.

Identical in behaviour to Spotipi Photo's, so a token made by either works in
both. Writes .cache-<username>, with the same scope getSongInfo.py reads.

Usage:
    python3 generateToken.py <spotify_username> [cache_path]

Expects SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET and SPOTIPY_REDIRECT_URI in
the environment -- generate-token.sh prompts for them and exports them.
"""

import os
import sys

from spotipy.oauth2 import SpotifyOAuth

# Must match SCOPE in getSongInfo.py. If you change one, change both.
SCOPE = "user-read-currently-playing"


def main():
    if len(sys.argv) < 2:
        print("usage: generateToken.py <spotify_username> [cache_path]")
        return 1

    username = sys.argv[1]
    cache_path = sys.argv[2] if len(sys.argv) > 2 else f".cache-{username}"

    missing = [v for v in ("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI")
               if not os.environ.get(v)]
    if missing:
        print("Missing environment variables: " + ", ".join(missing))
        print("Run generate-token.sh instead -- it prompts for these.")
        return 1

    auth = SpotifyOAuth(scope=SCOPE, username=username, cache_path=cache_path,
                        open_browser=False)
    token = auth.get_access_token(as_dict=False)
    if not token:
        print("No token returned -- the login did not complete.")
        return 1

    print()
    print("###### Spotify token created ######")
    print(f"Scope    : {SCOPE}")
    print(f"Filename : {os.path.abspath(cache_path)}")
    print()
    print("Give that full path to install_pi.sh when it asks for the token path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
