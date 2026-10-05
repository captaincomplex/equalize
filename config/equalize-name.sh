#!/bin/bash
# equalize-name.sh -- announce "equalize.local" on the home network as a
# second name for this Pi, next to its own (e.g. spotipi.local).
#
# avahi-publish keeps the name up for as long as it runs. The Pi's address
# can change (the router hands them out), so this checks every 30 seconds and
# re-announces when it does. Run by equalize-name.service.
set -u
NAME="${1:-equalize.local}"
current=""
pid=""
while true; do
  ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  if [ -n "$ip" ] && [ "$ip" != "$current" ]; then
    [ -n "$pid" ] && kill "$pid" 2>/dev/null
    avahi-publish -a -R "$NAME" "$ip" &
    pid=$!
    current=$ip
    echo "announcing $NAME at $ip"
  elif [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
    current=""                                   # it stopped: announce again
  fi
  sleep 30
done
