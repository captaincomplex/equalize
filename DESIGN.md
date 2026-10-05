# Design: the Equalize control panel

Recorded from the built page (python/client/templates/index.html), 4 Oct 2026.
Skins share one structure; `ui` in state.json picks one, switched from the
header: "rack" (the default, chosen by the owner), "player", and two
concepts under consideration, "daylight" and "silver". The LED panel itself
is unaffected.

## Structure (both skins)
- Header: the name, and the Rack / Player switch.
- Units, top to bottom: Panel (live snapshot + status readout), Display,
  Look, Share (only with Spotipi Photo), Sound, Schedule.
- Controls: push-button rows (`.seg`), sliders, style tiles, colour swatches,
  on/off switches, number/time fields. Everything saves on change; a short
  acknowledgement appears ("Saved" / "Couldn't reach the Pi").
- Touch targets 44px or more. Fonts are served by the Pi (static/fonts, OFL).

## Rack: studio rack units
- Ground #0f1012; unit face #1d1f22 to #26292d; ear #17191b with two screws
  and the unit name engraved vertically.
- Legends #d6d9dd, secondary #9aa0a8. Readouts amber #ffb020 on #0b0c0d.
- Colour only as signal: LED green #39d353 = selected / on; amber = readout
  and focus; red #ff4b3e = not running.
- Type: Barlow Semi Condensed, upper case, tracked, for labels; Barlow for
  prose; Share Tech Mono for numbers.
- Push buttons carry an LED above the legend that lights when chosen; faders
  have a capped thumb; style names sit on black label tape, green when chosen.

## Player: early-2000s media player
- Desk #1b1e22; window chrome #3a3f47 with light #6a727d / dark #111316
  bevel edges; title bars #121417 with grip lines.
- LCD readouts green #3cff5c (dim #239a39) on black.
- Type: Silkscreen for title bars, labels and buttons; Barlow for prose;
  Share Tech Mono in the LCD.
- Buttons are raised bevels that sink and turn to LCD when chosen; ticks are
  drawn boxes; the acknowledgement is a status bar along the bottom.

## Daylight (concept): pale 1960s German hi-fi, at full strength
- Ground #f3f0e9, ink #161615, secondary #5a5750, slots #e2ddd2.
- Barlow, lower case, set big: a 46px name, 34px section titles, 24-30px
  numbers. Heavy black rules (6px under the header, 3px between sections)
  instead of cards.
- One orange #e8590c that fills whatever is chosen: pill buttons, slider
  knobs, switches, tile outlines, the acknowledgement.

## Silver (concept): a 1970s receiver
- Brushed aluminium faces (#d9dbdd to #b9bcc0) on #2a2c2f; engraved black
  tracked legends; amber #ffb347 readouts in dark meter windows.
- Raised silver push buttons that go dark and amber when pressed; black
  knurled knobs on the sliders, orange #ff6a1a fill.

## Logo
Three logos (image/build_logos.py), chosen in the control panel's Logo
section: LED ring (default), Ring (teal on deep blue-green), LED grid. The
header and every icon follow the choice.

## Rules
- Brand colour never decorates: it only says what is on, chosen or wrong.
- No glows except on lit LEDs; no gradients except the hardware's own shading.
