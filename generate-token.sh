#!/bin/bash
# generate-token.sh -- OPTIONAL one-off Spotify login for Equalize.
#
# Equalize works without Spotify. A login adds three things: the
# "Spotify only" display mode, the song name on the web dashboard, and the
# "album" colour theme (bar colours taken from the album cover).
#
# Already have Spotipi Photo? Its .cache-<username> file works here as-is --
# same scope -- so copy it across instead of running this. Spotify now allows
# one developer app per account, so reusing Spotipi Photo's app is the way.
#
#     cd ~/equalize
#     bash generate-token.sh
set -u

cd "$(dirname "$0")"

if ! python3 -c "import spotipy" 2>/dev/null; then
  echo "==> Installing the spotipy library"
  sudo apt-get install -y python3-spotipy >/dev/null 2>&1 \
    || { echo "! Could not install python3-spotipy. Install it, then re-run this."; exit 1; }
fi

echo
echo "From your Spotify app at https://developer.spotify.com/dashboard"
echo "(Settings -> Basic Information). Nothing is sent anywhere but Spotify."
echo

read -rp "Spotify Client ID: "     SPOTIPY_CLIENT_ID
read -rp "Spotify Client Secret: " SPOTIPY_CLIENT_SECRET
read -rp "Spotify Redirect URI:  " SPOTIPY_REDIRECT_URI
read -rp "Spotify username:      " SPOTIFY_USERNAME

export SPOTIPY_CLIENT_ID SPOTIPY_CLIENT_SECRET SPOTIPY_REDIRECT_URI

if [ -z "${SPOTIFY_USERNAME}" ]; then
  echo "! A username is required -- the token file is named after it."
  exit 1
fi

echo
echo "==> A long https://accounts.spotify.com/... URL follows."
echo "    1. Open it in a browser on any device and log in / click Agree."
echo "    2. Your browser will jump to your redirect address, which will look"
echo "       like a page that FAILED TO LOAD. That is expected and correct."
echo "    3. Copy that entire address from the address bar and paste it back"
echo "       here, then press Enter."
echo

python3 python/generateToken.py "${SPOTIFY_USERNAME}" ".cache-${SPOTIFY_USERNAME}"
