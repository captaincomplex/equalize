# Glossary

Every technical term in Equalize, in plain English.

**AirPlay 2.** Apple's system for sending sound over Wi-Fi to speakers. The "2"
added multi-room: one iPhone can play to several speakers at once, and Apple's
protocol gives them all a shared clock so they stay in step. Equalize relies on
exactly that: the Pi is one of the speakers in the group.

**ALSA.** The part of Linux that handles sound devices. Programs play to and
record from "ALSA devices", named like `hw:Loopback,0,0` (card, device,
sub-device).

**ALSA loopback (`snd-aloop`).** A virtual cable inside the Pi: sound played
into one end comes out of the other as if recorded. shairport-sync plays into
it; Equalize records from it. No real audio hardware is involved.

**arecord.** A small standard Linux program that records from an ALSA device.
Equalize runs it to read the loopback.

**Automatic gain.** Turning the volume of the *picture* up or down so that loud
and quiet songs both fill the panel. Equalize tracks the loudest recent sound
and scales to it, but never boosts beyond a floor, so a fade-out doesn't turn
into dancing bars.

**Band.** A range of frequencies drawn as one bar. Equalize spaces them
logarithmically: each bar covers a similar number of musical notes, which is
how ears hear pitch.

**Chain / chain_length.** Plugging a second LED panel into the first one's
output so the two act as one wider screen. Two 64×64 panels chained = 128×64.

**Decibel (dB).** A scale for loudness that matches how ears work: every 10 dB
is ten times the power. Bar heights are worked out in decibels.

**FFT (Fast Fourier Transform).** The maths that takes a slice of sound (about a
twentieth of a second) and says how much of it is at each frequency: how much
bass, how much treble. It's the heart of every equaliser display.

**Frame rate (fps).** How many new pictures are drawn per second. Equalize aims
for 40.

**Frequency / Hz.** How fast a sound vibrates: low for bass (50 Hz), high for
cymbals (10,000 Hz = 10 kHz).

**GPIO.** The Pi's row of pins for driving electronics directly. The LED panel
is driven through them, which is why the display program runs as the root
(administrator) user.

**Hand-over (panel sharing).** When Spotipi Photo and Equalize share a Pi, the
small `equalize-panel` program stops one and starts the other, triggered by
AirPlay starting and stopping.

**Loopback.** See *ALSA loopback*.

**NQPTP.** A small companion program shairport-sync needs for AirPlay 2: it
keeps the Pi's clock in step with the other speakers in the group.

**Peak caps.** The single dots that hang above each bar at its recent highest
point, then drop. Borrowed from hi-fi graphic equalisers.

**Pinned release tag.** Building a specific, named release of someone else's
software (shairport-sync 5.5.2) rather than "whatever's newest today", so every
install gets the same, tested thing.

**Vaporwave.** A 2010s visual style borrowing from 1980s computer graphics:
a striped setting sun, a neon grid floor running to the horizon, and a palette
of pink, purple and cyan. Equalize's logo, web panel and default *vapor* LED
colours use it.

**Sample rate.** How many times per second sound is measured when it's digital.
Equalize uses 48,000.

**shairport-sync.** Open-source software that makes a Linux computer act as an
AirPlay speaker. Actively maintained; version 5.5.2 was released 9 Sep 2026.

**Sonos.** Your speakers. Most current Sonos models accept AirPlay 2, which is
what lets the iPhone play to a Sonos and the Pi together.

**Spotify Connect.** Spotify's own way of playing on another device (your
Sonos). The music then goes from Spotify's servers straight to the speaker,
which is why nothing else in the house can see it. Equalize uses AirPlay
instead for that reason.

**sudo / sudoers.** `sudo` runs one command as the administrator. A sudoers
rule says exactly which commands a given user may run that way; Equalize's
lets the AirPlay receiver run the panel hand-over, and nothing else.

**systemd service.** A program Linux starts at boot and restarts if it crashes.
Equalize has two (`equalize` and `equalize-web`), plus shairport-sync's own.

**Token (Spotify).** The saved login that lets Equalize ask Spotify "what's
playing?" without your password. Optional in Equalize.

**Spotify Connect.** Spotify's own way of playing on another device: you pick
the device in the Spotify app, and that device fetches and plays the music
itself. The phone is only the remote control.

**librespot / Raspotify.** librespot is free software that makes a computer
appear as a Spotify Connect device. Raspotify packages it for Raspberry Pi
and keeps it updated.

**OwnTone.** A free music server. Here it takes the music librespot plays and
sends it on to your speakers over AirPlay 2, and writes an in-step copy for
the LED panel.

**Named pipe (FIFO).** A file that is really a tube: one program writes into
it and another reads out of it, without anything being stored.
