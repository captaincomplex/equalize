# TODO

## First build on real hardware (needs a Pi, a panel and a Sonos)
- [ ] Run `install_pi.sh` on fresh Raspberry Pi OS Lite (trixie, 64-bit). Record
      how long the shairport-sync build takes on a Pi 3A+.
- [ ] Confirm "Equalize" appears in the iPhone AirPlay picker alongside the Sonos,
      and both can be ticked together.
- [ ] Confirm the loopback delivers audio (dashboard: *Sound: music arriving*).
- [ ] Check by eye that bass hits line up with the Sonos; tune
      `audio_backend_latency_offset_in_seconds` (starts at -0.05, an estimate).
- [ ] Confirm that when AirPlay stops, the loopback sends silence or stops
      (either way the bars should fall within 3 s; the code handles both).
- [ ] Check the frame rate and CPU temperature on a Pi 3A+ while AirPlay plays.
- [ ] Try 64×32 and 128×64 panels, if available.
- [ ] Look at each style (sunset, disc, meter, equals) on the real LEDs; the
      faint "unlit" meter segments and the grid floor may need brightness tweaks.

## Sharing with Spotipi Photo (same Pi)
- [ ] Check the Pi's OS first (`cat /etc/os-release`). Spotipi Photo's notes say
      it runs Raspbian Buster; Equalize is built for Raspberry Pi OS trixie.
- [ ] Time the hand-over in each direction (AirPlay start -> bars; stop -> covers).
- [ ] Confirm shairport-sync's active-state hooks fire as expected via sudo
      (`journalctl -u shairport-sync`), and that `equalize-panel status` agrees.

## Possible later
- [ ] Spotify Connect route (librespot + OwnTone forwarding to the Sonos by
      AirPlay 2) for Android phones and guests, and so the phone can leave the
      house. Researched 28 Sep 2026: OwnTone's fifo output is timed to match
      its AirPlay outputs; librespot 0.8.0 needs Premium.
- [x] More styles: Mirror, Wave, Waterfall, Needle (4 Oct 2026), and eight more
      colour themes.
- [ ] Look at the new styles on the real LEDs: the Needle's dim dial face and
      the Wave's dotted peak line may need brightness tweaks.
- [ ] Auto-updater (as Spotipi Photo has).
