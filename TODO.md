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
- [x] Spotify Connect route (Raspotify + OwnTone forwarding by AirPlay 2),
      built 5 Oct 2026, opt-in in install_pi.sh. Tested off-Pi: OwnTone 29.3
      builds, installs and runs with config/owntone.conf; a tone fed into the
      librespot pipe reaches Equalize's reader in 2.3 s, unchanged.
- [ ] Spotify Connect on the real Pi: Raspotify itself couldn't be fetched
      in the test sandbox (its network blocks dtcooper.github.io). Check:
      "Equalize" in Spotify's device list; the Sonos in Spotify speakers;
      bars in step with the Sonos; the panel handing over on play/stop.
- [x] More styles: Mirror, Wave, Waterfall, Needle (4 Oct 2026), and eight more
      colour themes.
- [ ] Look at the new styles on the real LEDs: the Needle's dim dial face, the
      Wave's dotted peak line, Trails' fade rate and Plasma's speed may need
      tweaks.
- [ ] Pick a logo from image/shortlist/sheet.png, then rebuild the icons.
- [ ] After the AirPlay byte-alignment fix, put Sensitivity back to the
      middle and see whether the bars still sit at the top.
- [ ] Auto-updater (as Spotipi Photo has).
