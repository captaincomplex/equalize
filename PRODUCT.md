# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Primarily the owner, tinkering often: changing styles, colours and settings
from a phone on the home network, usually while music is playing and the LED
panel is in view across the room. Others in the household may use it
occasionally.

## Product Purpose
Equalize draws a graphic equaliser on an RGB LED panel on a Raspberry Pi,
from music sent to the Pi over AirPlay alongside the household's speakers.
The control panel (served by the Pi on the local network) chooses how it
looks and behaves. Success: the panel on the wall looks the way the owner
wants, and changing it is quick and certain.

## Positioning
The Pi joins the AirPlay group as a silent speaker, so the bars come from
the real audio, in time with the speakers, with no microphone. Shares a Pi
and its LED panel with Spotipi Photo, taking turns.

## Operating Context
Phone browser on the home Wi-Fi, at http://<pi-name>.local:8080 when
sharing with Spotipi Photo (which keeps port 80). The panel itself is the
real output; the page shows a live snapshot and stills of each style.

## Capabilities and Constraints
- Flask + Jinja templates, no build step, no external CDNs: everything is
  served by the Pi itself, which may have no internet.
- Settings: display mode, brightness, style (9), colours (14 incl. album
  cover from Spotify), bar count, sensitivity, peak caps, panel sharing with
  Spotipi Photo, sound source, screen timer, quiet hours, sunrise/sunset
  dimmer.
- Panels 64x32, 32x64, 64x64, 128x64, 64x128.
- Spotify login is optional.

## Brand Commitments
Free and open source (MIT), part of the xpdr.aero family of projects on
GitHub. The owner's real name never appears. Name: Equalize. Logo not yet
chosen (image/shortlist/). The owner finds the current purple, vaporwave
look too generic; it is not a commitment.

## Evidence on Hand
Style GIFs in docs/, logo shortlist in image/shortlist/. No users,
testimonials or reviews exist; none may be invented.

## Product Principles
1. The panel on the wall is the point; the page serves it.
2. A change made on the phone shows on the panel within a second, and the
   page says so.
3. One good default for everything; the rest is there for tinkering.
4. Nothing leaves the house.
