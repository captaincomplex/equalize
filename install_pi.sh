#!/bin/bash
# install_pi.sh -- install Equalize on a Raspberry Pi.
#
# Written for Raspberry Pi OS (64-bit) based on Debian 13 "trixie", the
# current release. Run from inside the equalize folder on the Pi:
#     cd ~/equalize
#     sudo bash install_pi.sh
#
# Safe to re-run: every step checks what's already there first.
#
# What it sets up:
#   1. Python libraries, from Raspberry Pi OS's own packages (apt).
#   2. The ALSA loopback -- a virtual audio cable inside the Pi.
#   3. NQPTP + shairport-sync, built from pinned release tags, so the Pi
#      shows up as an AirPlay 2 speaker called "Equalize".
#   4. Onboard sound off (the LED panel needs its timing circuit).
#   5. Two services: equalize (the display) and equalize-web (control panel).
set -u   # deliberately not -e: report each step's problem and carry on

# ---- Pinned versions. Checked 28 Sep 2026: newest stable release tags. ----
SHAIRPORT_TAG="5.5.2"       # released 9 Sep 2026
NQPTP_TAG="1.2.8"           # released 13 May 2026

INSTALL_PATH="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR=/usr/local/src
NEEDS_REBOOT=0
PROBLEMS=()

say()  { echo; echo "==> $*"; }
note() { echo "    $*"; }
problem() { echo "    ! $*"; PROBLEMS+=("$*"); }

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo:  sudo bash install_pi.sh"; exit 1
fi

. /etc/os-release 2>/dev/null
note "System: ${PRETTY_NAME:-unknown}"
if [ "${VERSION_CODENAME:-}" != "trixie" ]; then
  note "This installer is written for Debian 13 'trixie' (current Raspberry Pi OS)."
  note "On '${VERSION_CODENAME:-unknown}' some steps may need doing by hand."
fi

# ---------------------------------------------------------------------------
say "Python libraries and audio tools (apt)"
apt-get update -qq
apt-get install -y --no-install-recommends \
  python3-numpy python3-pil python3-flask python3-requests python3-spotipy \
  alsa-utils git \
  || problem "apt could not install some Python packages -- see the messages above"

# ---------------------------------------------------------------------------
say "ALSA loopback (the virtual cable between AirPlay and the display)"
echo "snd-aloop" > /etc/modules-load.d/equalize.conf
# A fixed card number keeps it from shuffling other sound devices around.
echo "options snd-aloop index=7 id=Loopback pcm_substreams=1" > /etc/modprobe.d/equalize-aloop.conf
if modprobe snd-aloop 2>/dev/null && grep -q Loopback /proc/asound/cards; then
  note "Loopback is live."
else
  note "Loopback will appear after a reboot."
  NEEDS_REBOOT=1
fi

# ---------------------------------------------------------------------------
say "Onboard sound off (the LED panel shares its timing circuit)"
BOOTCFG=/boot/firmware/config.txt
[ -f "$BOOTCFG" ] || BOOTCFG=/boot/config.txt
if [ -f "$BOOTCFG" ]; then
  if grep -q "^dtparam=audio=off" "$BOOTCFG"; then
    note "Already off."
  else
    if grep -q "^dtparam=audio=on" "$BOOTCFG"; then
      sed -i 's/^dtparam=audio=on/dtparam=audio=off/' "$BOOTCFG"
    else
      echo "dtparam=audio=off" >> "$BOOTCFG"
    fi
    note "Set dtparam=audio=off in $BOOTCFG."
    NEEDS_REBOOT=1
  fi
else
  problem "Could not find config.txt -- add dtparam=audio=off to it by hand."
fi

# ---------------------------------------------------------------------------
say "AirPlay 2 receiver: NQPTP ${NQPTP_TAG} + shairport-sync ${SHAIRPORT_TAG}"
note "(Building from source takes 10-20 minutes on a Pi 3. Only done once.)"

apt-get install -y --no-install-recommends build-essential autoconf automake libtool \
  libpopt-dev libconfig-dev libasound2-dev avahi-daemon avahi-utils libavahi-client-dev libssl-dev \
  libsoxr-dev libplist-dev libsodium-dev uuid-dev libgcrypt-dev xxd libplist-utils \
  libavutil-dev libavcodec-dev libavformat-dev systemd-dev \
  || problem "apt could not install the AirPlay build tools"

build_tag() {   # build_tag <name> <repo> <tag> <configure args...>
  local name=$1 repo=$2 tag=$3; shift 3
  mkdir -p "$SRC_DIR"
  if [ ! -d "$SRC_DIR/$name/.git" ]; then
    git clone -q "$repo" "$SRC_DIR/$name" || { problem "could not download $name"; return 1; }
  fi
  ( cd "$SRC_DIR/$name" \
    && git fetch -q --tags origin \
    && git checkout -q "refs/tags/$tag" \
    && autoreconf -fi >/dev/null 2>&1 \
    && ./configure "$@" >/dev/null \
    && { make clean >/dev/null 2>&1 || true; } \
    && make -j"$(nproc)" >/dev/null \
    && make install >/dev/null ) \
    || { problem "building $name $tag failed -- run the steps in $SRC_DIR/$name by hand to see why"; return 1; }
  note "$name $tag installed."
}

if nqptp -V 2>/dev/null | grep -q "^Version: ${NQPTP_TAG}"; then
  note "nqptp ${NQPTP_TAG} already installed."
else
  build_tag nqptp https://github.com/mikebrady/nqptp.git "$NQPTP_TAG" --with-systemd-startup
fi
systemctl enable --now nqptp >/dev/null 2>&1 || problem "nqptp service would not start"

if shairport-sync -V 2>/dev/null | grep -q "^${SHAIRPORT_TAG}"; then
  note "shairport-sync ${SHAIRPORT_TAG} already installed."
else
  build_tag shairport-sync https://github.com/mikebrady/shairport-sync.git "$SHAIRPORT_TAG" \
    --sysconfdir=/etc --with-alsa --with-soxr --with-avahi --with-ssl=openssl \
    --with-systemd-startup --with-airplay-2
fi

if [ -f /etc/shairport-sync.conf ] && ! grep -q "Equalize's settings" /etc/shairport-sync.conf; then
  cp /etc/shairport-sync.conf "/etc/shairport-sync.conf.before-equalize"
  note "Kept the previous config as /etc/shairport-sync.conf.before-equalize"
fi
cp "${INSTALL_PATH}/config/shairport-sync.conf" /etc/shairport-sync.conf
systemctl enable shairport-sync >/dev/null 2>&1
systemctl restart shairport-sync 2>/dev/null \
  || note "shairport-sync will start after the reboot (it needs the loopback)."

# Wi-Fi power saving makes AirPlay speakers drop out of the picker.
if command -v nmcli >/dev/null; then
  for c in $(nmcli -t -f NAME,TYPE connection show | awk -F: '$2=="802-11-wireless"{print $1}'); do
    nmcli connection modify "$c" 802-11-wireless.powersave 2 2>/dev/null \
      && note "Wi-Fi power saving off for '$c'."
  done
fi

# ---------------------------------------------------------------------------
say "LED matrix driver"
PYTHON=""
for p in /usr/bin/python3 /home/*/env/bin/python3 /root/env/bin/python3; do
  [ -x "$p" ] && "$p" -c "import rgbmatrix" 2>/dev/null && { PYTHON=$p; break; }
done
if [ -n "$PYTHON" ]; then
  note "rgbmatrix found for $PYTHON"
else
  PYTHON=/usr/bin/python3
  problem "The LED driver (rgbmatrix) isn't installed yet. Install it with Adafruit's installer, then re-run this script:"
  cat <<'EOF'

      sudo apt install -y python3-pip python3-venv git
      cd ~
      python3 -m venv env --system-site-packages
      source env/bin/activate
      pip3 install --upgrade setuptools adafruit-python-shell click
      git clone https://github.com/adafruit/Raspberry-Pi-Installer-Scripts.git
      cd Raspberry-Pi-Installer-Scripts
      sudo -E env PATH=$PATH python3 rgb-matrix.py

    Answer: Bonnet, then Convenience (or Quality if you've soldered the
    GPIO4-GPIO18 wire). Then:  cd ~/equalize && sudo bash install_pi.sh
EOF
fi
"$PYTHON" -c "import numpy, PIL, flask, requests" 2>/dev/null \
  || problem "$PYTHON can't import numpy/PIL/flask/requests"

# ---------------------------------------------------------------------------
say "Spotify (optional)"
note "Adds the 'Spotify only' mode, the song name, and album-cover colours."
note "Leave blank and press Enter to skip. You can re-run this script later."
SP_ARGS=""
read -rp "    Spotify username (blank to skip): " SPOTIFY_USERNAME
if [ -n "${SPOTIFY_USERNAME}" ]; then
  read -rp "    Full path to the token (.cache-...) file: " TOKEN_PATH
  read -rp "    Spotify Client ID: " SPOTIFY_CLIENT_ID
  read -rp "    Spotify Client Secret: " SPOTIFY_CLIENT_SECRET
  read -rp "    Spotify Redirect URI: " SPOTIFY_REDIRECT_URI
  if [ -f "${TOKEN_PATH}" ]; then
    SP_ARGS="${SPOTIFY_USERNAME} ${TOKEN_PATH}"
  else
    problem "No token file at '${TOKEN_PATH}' -- skipping Spotify. Run generate-token.sh, then re-run this."
  fi
fi

# ---------------------------------------------------------------------------
say "Sharing a Pi with Spotipi Photo?"
PORT=80
if [ -e /etc/systemd/system/spotipi.service ]; then
  SHARED=1
  note "Spotipi Photo is installed here too. Only one program can drive the"
  note "LED panel, so they'll take turns: by default Equalize while AirPlay"
  note "music plays, Spotipi Photo the rest of the time. Change it any time"
  note "in Equalize's control panel, under 'Sharing with Spotipi Photo'."
else
  SHARED=0
fi
# Spotipi Photo's own control panel always has port 80, so with it here
# Equalize's is on 8080 -- every time, including re-runs (an earlier version
# moved it back to 80 on a re-run, where it could never start).
if [ "$SHARED" = "1" ]; then
  PORT=8080
  note "Both control panels will answer on the normal address: a small front"
  note "door on port 80 sends equalize.local to Equalize's panel (8080) and"
  note "spotipi.local to Spotipi Photo's (moved to 8081)."
elif ss -ltn 2>/dev/null | grep -q ':80 ' && ! systemctl is-active --quiet equalize-web; then
  PORT=8080
  note "Port 80 is taken by something else: using 8080."
fi

# ---------------------------------------------------------------------------
say "Services"
mkdir -p "${INSTALL_PATH}/config"
chmod 777 "${INSTALL_PATH}/config" 2>/dev/null

systemctl stop equalize equalize-web 2>/dev/null
rm -rf /etc/systemd/system/equalize.service.d
cp "${INSTALL_PATH}/config/equalize.service" /etc/systemd/system/
sed -i "/\[Service\]/a WorkingDirectory=${INSTALL_PATH}/python" /etc/systemd/system/equalize.service
sed -i "/\[Service\]/a ExecStart=${PYTHON} ${INSTALL_PATH}/python/equalize.py ${SP_ARGS}" /etc/systemd/system/equalize.service
if [ -n "${SP_ARGS}" ]; then
  mkdir -p /etc/systemd/system/equalize.service.d
  cat > /etc/systemd/system/equalize.service.d/spotify.conf <<EOF
[Service]
Environment="SPOTIPY_CLIENT_ID=${SPOTIFY_CLIENT_ID}"
Environment="SPOTIPY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET}"
Environment="SPOTIPY_REDIRECT_URI=${SPOTIFY_REDIRECT_URI}"
EOF
  chmod 600 /etc/systemd/system/equalize.service.d/spotify.conf
fi

cp "${INSTALL_PATH}/config/equalize-web.service" /etc/systemd/system/
sed -i "/\[Service\]/a WorkingDirectory=${INSTALL_PATH}/python/client" /etc/systemd/system/equalize-web.service
sed -i "/\[Service\]/a ExecStart=${PYTHON} ${INSTALL_PATH}/python/client/app.py" /etc/systemd/system/equalize-web.service
sed -i "/\[Service\]/a Environment=EQUALIZE_PORT=${PORT}" /etc/systemd/system/equalize-web.service

# The panel switch: decides at boot, and whenever AirPlay starts or stops,
# whether Equalize or Spotipi Photo drives the panel (see config/equalize-panel).
sed "s|@STATE_PATH@|${INSTALL_PATH}/config/state.json|" \
  "${INSTALL_PATH}/config/equalize-panel" > /usr/local/bin/equalize-panel
chmod 755 /usr/local/bin/equalize-panel
cp "${INSTALL_PATH}/config/equalize-panel.service" /etc/systemd/system/
# The AirPlay receiver runs as its own user; this lets it call the switch
# (and only the switch). visudo checks the rule before it goes live.
cp "${INSTALL_PATH}/config/equalize-panel.sudoers" /tmp/equalize-panel.sudoers
if visudo -cf /tmp/equalize-panel.sudoers >/dev/null; then
  install -m 440 /tmp/equalize-panel.sudoers /etc/sudoers.d/equalize-panel
else
  problem "the sudoers rule for panel sharing failed its check -- sharing won't switch automatically"
fi
rm -f /tmp/equalize-panel.sudoers

systemctl daemon-reload
systemctl enable equalize-web >/dev/null 2>&1
systemctl restart equalize-web

# A second name for this Pi, so the panel is at http://equalize.local
if [ "$(hostname)" != "equalize" ]; then
  cp "${INSTALL_PATH}/config/equalize-name.service" /etc/systemd/system/
  sed -i "/\[Service\]/a ExecStart=/bin/bash ${INSTALL_PATH}/config/equalize-name.sh equalize.local" /etc/systemd/system/equalize-name.service
  systemctl daemon-reload
  systemctl enable equalize-name >/dev/null 2>&1
  systemctl restart equalize-name || problem "couldn't announce equalize.local -- use http://$(hostname).local:${PORT} instead"
fi

# Sharing with Spotipi Photo: Spotipi Photo's panel moves to 8081 and the
# front door takes port 80, passing each visit to the panel whose name was
# typed. (Spotipi Photo's installer leaves this setting alone on re-runs.)
if [ "$SHARED" = "1" ]; then
  mkdir -p /etc/systemd/system/spotipi-client.service.d
  printf '[Service]\nEnvironment=SPOTIPI_PORT=8081\n' > /etc/systemd/system/spotipi-client.service.d/equalize-door.conf
  cp "${INSTALL_PATH}/config/equalize-door.service" /etc/systemd/system/
  sed -i "/\[Service\]/a ExecStart=${PYTHON} ${INSTALL_PATH}/python/door.py --port 80 --equalize 8080 --spotipi 8081" /etc/systemd/system/equalize-door.service
  systemctl daemon-reload
  systemctl restart spotipi-client          # off port 80 first...
  systemctl enable equalize-door >/dev/null 2>&1
  systemctl restart equalize-door           # ...then the door takes it
fi
# Neither display starts by itself any more: equalize-panel picks one.
systemctl disable equalize >/dev/null 2>&1
[ "$SHARED" = "1" ] && systemctl disable spotipi >/dev/null 2>&1
systemctl enable equalize-panel >/dev/null 2>&1
/usr/local/bin/equalize-panel boot

# ---------------------------------------------------------------------------
HOST=$(hostname)
echo
echo "Done."
if [ "$SHARED" = "1" ] || [ "$PORT" = 80 ]; then
  echo "  Control panel : http://equalize.local"
else
  echo "  Control panel : http://equalize.local:${PORT}"
fi
echo "  Display       : sudo systemctl status equalize"
[ "$SHARED" = "1" ] && echo "  Panel sharing : equalize-panel status    (Spotipi Photo's panel: http://${HOST}.local)"
echo "  AirPlay       : sudo systemctl status shairport-sync"
echo
echo "  To use: on your iPhone, open the AirPlay picker and tick BOTH your"
echo "  Sonos speaker AND 'Equalize'. Play something. The bars follow."
if [ ${#PROBLEMS[@]} -gt 0 ]; then
  echo
  echo "  Things that need attention:"
  for p in "${PROBLEMS[@]}"; do echo "    - $p"; done
fi
if [ "$NEEDS_REBOOT" = "1" ]; then
  echo
  echo "  Reboot to finish:  sudo reboot"
fi
