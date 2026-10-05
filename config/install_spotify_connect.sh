#!/bin/bash
# install_spotify_connect.sh -- the Spotify Connect route. Run by install_pi.sh
# (it asks first); safe to re-run: every step checks what's already there.
#
#   Spotify app --("Equalize")--> librespot, from Raspotify
#     --> /srv/equalize/spotify (a named pipe)
#     --> OwnTone --> your speakers over AirPlay 2 (chosen in the control panel)
#               \--> /var/lib/equalize/owntone-out.fifo, in step --> the LED panel
#
# Versions, checked 5 Oct 2026:
#   OwnTone 29.3 (22 Jul 2026), built from its release tarball, pinned below.
#   Raspotify from its own apt repository, NOT pinned: Spotify changes how it
#   delivers music now and then, and an old librespot then stops playing
#   (Raspotify 0.48.2, Jul 2026: "Fixes broken audio CDN"). librespot's last
#   tagged release, 0.8.0 (Nov 2025), predates that fix, so following
#   Raspotify's updates is the safer choice. Recorded in README, "Decisions".
#
#   sudo bash config/install_spotify_connect.sh <equalize folder> <python>
set -u
OWNTONE_TAG="29.3"
INSTALL_PATH="${1:?equalize folder}"
PYTHON="${2:-/usr/bin/python3}"
SRC_DIR=/usr/local/src
FAILED=0

note()  { echo "    $*"; }
fail()  { echo "    ! $*"; FAILED=1; }

# ---- the two pipes -------------------------------------------------------
install -d -m 755 /srv/equalize
[ -p /srv/equalize/spotify ] || mkfifo -m 666 /srv/equalize/spotify
chmod 666 /srv/equalize/spotify

# ---- Raspotify (librespot) ----------------------------------------------
if ! dpkg -s raspotify >/dev/null 2>&1; then
  note "Adding Raspotify's package source..."
  curl -sSfL https://dtcooper.github.io/raspotify/key.asc -o /usr/share/keyrings/raspotify_key.asc \
    && chmod 644 /usr/share/keyrings/raspotify_key.asc \
    && echo "deb [signed-by=/usr/share/keyrings/raspotify_key.asc] https://dtcooper.github.io/raspotify raspotify main" \
         > /etc/apt/sources.list.d/raspotify.list \
    && apt-get update -qq \
    && apt-get install -y -qq raspotify >/dev/null \
    || fail "couldn't install Raspotify"
fi
if [ -d /etc/raspotify ]; then
  [ -f /etc/raspotify/conf ] && ! grep -q "Equalize's settings" /etc/raspotify/conf \
    && cp /etc/raspotify/conf /etc/raspotify/conf.before-equalize
  cp "${INSTALL_PATH}/config/raspotify.conf" /etc/raspotify/conf
  mkdir -p /etc/systemd/system/raspotify.service.d
  cp "${INSTALL_PATH}/config/raspotify-override.conf" /etc/systemd/system/raspotify.service.d/equalize.conf
  note "Raspotify: shows up in Spotify as \"Equalize\"."
fi

# ---- OwnTone ---------------------------------------------------------------
if owntone -v 2>/dev/null | grep -q "^owntone ${OWNTONE_TAG}\$"; then
  note "OwnTone ${OWNTONE_TAG} already installed."
else
  note "Building OwnTone ${OWNTONE_TAG} (about 10 minutes on a Pi 4)..."
  apt-get install -y -qq --no-install-recommends \
    build-essential gettext gawk gperf bison flex libconfuse-dev libunistring-dev libsqlite3-dev \
    libavcodec-dev libavformat-dev libavfilter-dev libswscale-dev libavutil-dev \
    libasound2-dev libxml2-dev libgcrypt20-dev libavahi-client-dev zlib1g-dev \
    libevent-dev libplist-dev libsodium-dev libjson-c-dev libwebsockets-dev \
    libcurl4-openssl-dev libprotobuf-c-dev avahi-daemon xz-utils >/dev/null \
    || fail "apt couldn't install OwnTone's build tools"
  mkdir -p "$SRC_DIR"
  ( cd "$SRC_DIR" \
    && curl -sSfL -o "owntone-${OWNTONE_TAG}.tar.xz" \
         "https://github.com/owntone/owntone-server/releases/download/${OWNTONE_TAG}/owntone-${OWNTONE_TAG}.tar.xz" \
    && rm -rf "owntone-${OWNTONE_TAG}" && tar xJf "owntone-${OWNTONE_TAG}.tar.xz" \
    && cd "owntone-${OWNTONE_TAG}" \
    && ./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var \
         --enable-install-user --disable-spotify >/dev/null \
    && make -j"$(nproc)" >/dev/null \
    && make install >/dev/null ) \
    || fail "building OwnTone ${OWNTONE_TAG} failed -- run the steps in ${SRC_DIR}/owntone-${OWNTONE_TAG} by hand to see why"
fi
if id owntone >/dev/null 2>&1; then
  install -d -m 755 -o owntone -g owntone /var/lib/equalize /var/cache/owntone
  [ -f /etc/owntone.conf ] && ! grep -q "Equalize's settings" /etc/owntone.conf \
    && cp /etc/owntone.conf /etc/owntone.conf.before-equalize
  cp "${INSTALL_PATH}/config/owntone.conf" /etc/owntone.conf
fi

# ---- the watcher that hands the panel over ------------------------------
cp "${INSTALL_PATH}/config/equalize-spotify-watch.service" /etc/systemd/system/
sed -i "/\[Service\]/a ExecStart=${PYTHON} ${INSTALL_PATH}/python/spotify_watch.py" \
  /etc/systemd/system/equalize-spotify-watch.service

systemctl daemon-reload
systemctl enable owntone raspotify equalize-spotify-watch >/dev/null 2>&1
systemctl restart owntone raspotify equalize-spotify-watch \
  || fail "a Spotify Connect service wouldn't start: journalctl -u owntone -u raspotify -n 40"
exit $FAILED
