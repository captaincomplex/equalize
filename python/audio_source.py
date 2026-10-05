"""
audio_source.py -- where the sound comes from. No microphone, ever.

AirPlaySource  the music your iPhone/iPad/Mac/Apple TV is sending to the
               "Equalize" AirPlay speaker. shairport-sync receives it and
               plays it into an ALSA loopback -- a virtual cable inside the
               Pi (the snd-aloop kernel module). We read the other end of that
               cable with `arecord`. The Pi makes no sound; your Sonos does.
SpotifySource  OwnTone's in-step copy of what Spotify Connect is playing.
MusicSource    both of the above: whichever is playing.
DemoSource     a made-up drum-and-bass-line pattern generated in code, for
               checking the panel before AirPlay is set up, and for
               tools/preview.py.

Both expose .samplerate, .error (None when healthy), .device_name,
.read(n) -> the newest n samples (mono float32, -1..1), and .close().

Timing: AirPlay 2 tells every speaker in a group exactly when to play each
moment of audio. shairport-sync honours that for the loopback just as it
would for a real speaker, so what arrives here lines up with the Sonos.
"""

import math
import shutil
import subprocess
import threading
import time

import numpy as np

# Both ends of the loopback must agree on format. install_pi.sh pins
# shairport-sync's output to exactly this (see config/shairport-sync.conf).
LOOP_DEVICE = "hw:Loopback,1,0"
LOOP_RATE = 48000
LOOP_CHANNELS = 2


FRAME_BYTES = LOOP_CHANNELS * 2        # one moment of sound: 2 bytes per ear


def to_mono(data):
    """Whole frames of 16-bit stereo -> mono floats, plus the bytes left over.

    A read from the pipe can stop part-way through a frame. Those bytes must
    be kept for the next read: dropping them shifts every later sample by a
    byte or two, which turns music into loud hiss and fills every bar.
    """
    usable = len(data) // FRAME_BYTES * FRAME_BYTES
    pcm = np.frombuffer(data[:usable], dtype="<i2")
    mono = pcm.reshape(-1, LOOP_CHANNELS).mean(axis=1) / 32768.0
    return mono.astype(np.float32), data[usable:]


class _Ring:
    """Fixed-size buffer that always holds the newest samples."""

    def __init__(self, size):
        self.buf = np.zeros(size, dtype=np.float32)
        self.lock = threading.Lock()

    def push(self, x):
        with self.lock:
            n = len(x)
            if n >= len(self.buf):
                self.buf[:] = x[-len(self.buf):]
            else:
                self.buf[:-n] = self.buf[n:]
                self.buf[-n:] = x

    def latest(self, n):
        with self.lock:
            return self.buf[-n:].copy()


class AirPlaySource:
    CHUNK_FRAMES = 480                  # 10 ms at 48 kHz

    def __init__(self, device=LOOP_DEVICE, buffer_size=8192):
        self.samplerate = LOOP_RATE
        self.device_name = "AirPlay (%s)" % device
        self.error = None
        self.ring = _Ring(buffer_size)
        self.last_data = 0.0
        self.proc = None
        self._stop = False
        if shutil.which("arecord") is None:
            self.error = "arecord not found (install alsa-utils)"
            return
        cmd = ["arecord", "-q", "-D", device, "-t", "raw", "-f", "S16_LE",
               "-c", str(LOOP_CHANNELS), "-r", str(LOOP_RATE),
               "--buffer-time=40000", "--period-time=10000"]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, bufsize=0)
        except OSError as e:
            self.error = "could not start arecord: %s" % e
            return
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        chunk = self.CHUNK_FRAMES * LOOP_CHANNELS * 2
        rest = b""
        while not self._stop:
            data = self.proc.stdout.read(chunk)
            if not data:
                err = self.proc.stderr.read().decode(errors="replace").strip()
                self.error = "loopback closed: %s" % (err or "arecord exited")
                return
            mono, rest = to_mono(rest + data)
            if len(mono):
                self.ring.push(mono)
            self.last_data = time.time()

    def read(self, n):
        # Audio older than a moment is stale: whether the loopback sends
        # silence or simply stops when nothing is playing, the bars must fall.
        if time.time() - self.last_data > 0.3:
            return np.zeros(n, dtype=np.float32)
        return self.ring.latest(n)

    def close(self):
        self._stop = True
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                pass
            self.proc = None


# Spotify Connect: librespot (via Raspotify) plays into OwnTone, which sends
# the music on to the speakers over AirPlay 2 and writes a copy, held back to
# play in step with them, into this pipe. 16-bit stereo at 44.1 kHz.
SPOTIFY_PIPE = "/var/lib/equalize/owntone-out.fifo"   # outside OwnTone's music folder
SPOTIFY_RATE = 44100


class SpotifySource:
    """Reads OwnTone's in-step copy of the music. OwnTone makes the pipe anew
    at the start of each session, so when the old one runs dry this simply
    opens the path again."""

    CHUNK = 4410 * 4                    # 100 ms of 16-bit stereo

    def __init__(self, path=SPOTIFY_PIPE, buffer_size=8192):
        self.samplerate = SPOTIFY_RATE
        self.device_name = "Spotify Connect (via OwnTone)"
        self.error = None
        self.path = path
        self.ring = _Ring(buffer_size)
        self.last_data = 0.0
        self._stop = False
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        # Opened without waiting (O_NONBLOCK), so a pipe that OwnTone has
        # already replaced can't leave us stuck waiting on the old one: every
        # half second we check the path still leads to the pipe we hold.
        import os
        import select
        while not self._stop:
            try:
                fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                time.sleep(1.0)
                continue
            inode = os.fstat(fd).st_ino
            rest = b""
            try:
                while not self._stop:
                    ready, _, _ = select.select([fd], [], [], 0.5)
                    if ready:
                        try:
                            data = os.read(fd, self.CHUNK)
                        except BlockingIOError:
                            data = None
                        if data:
                            mono, rest = to_mono(rest + data)
                            if len(mono):
                                self.ring.push(mono)
                            self.last_data = time.time()
                            continue
                        time.sleep(0.05)                 # no writer just now
                    try:
                        if os.stat(self.path).st_ino != inode:
                            break                        # OwnTone made a new pipe
                    except FileNotFoundError:
                        break
            finally:
                os.close(fd)

    def read(self, n):
        if time.time() - self.last_data > 0.3:
            return np.zeros(n, dtype=np.float32)
        return self.ring.latest(n)

    def close(self):
        self._stop = True


class MusicSource:
    """AirPlay and Spotify Connect at once: draws whichever is playing. If
    both are (unlikely), the one that was playing first keeps the panel."""

    def __init__(self, airplay=None, spotify=None):
        self.airplay = airplay if airplay is not None else AirPlaySource()
        self.spotify = spotify if spotify is not None else SpotifySource()
        self.current = self.airplay

    def _live(self, s):
        return time.time() - getattr(s, "last_data", 0) <= 0.3

    def _active(self):
        # Stay with the one playing; move only when it goes quiet and the
        # other is playing.
        if not self._live(self.current):
            other = self.spotify if self.current is self.airplay else self.airplay
            if self._live(other):
                self.current = other
        return self.current

    @property
    def samplerate(self):
        return self._active().samplerate

    @property
    def device_name(self):
        a = self._active()
        return a.device_name if time.time() - getattr(a, "last_data", 0) <= 0.3 else "AirPlay or Spotify Connect"

    @property
    def error(self):
        return self.airplay.error

    @property
    def via(self):
        """'airplay', 'spotify' or None: where the music is coming from now."""
        a = self._active()
        if time.time() - getattr(a, "last_data", 0) > 0.3:
            return None
        return "spotify" if a is self.spotify else "airplay"

    def read(self, n):
        return self._active().read(n)

    def close(self):
        self.airplay.close()
        self.spotify.close()


class DemoSource:
    """A synthetic 120 bpm pattern: kick drum, bass line, hi-hats, pad."""

    BPM = 120.0
    BASS = [55.0, 55.0, 82.4, 73.4, 65.4, 65.4, 98.0, 87.3]      # A1 A1 E2 D2 C2 C2 G2 F2

    def __init__(self, samplerate=LOOP_RATE):
        self.samplerate = samplerate
        self.error = None
        self.device_name = "demo pattern"
        self.rng = np.random.default_rng(1)

    def signal(self, t):
        """Sound at the times in array t (seconds)."""
        beat = 60.0 / self.BPM
        pos = np.mod(t, beat)                                   # time since the beat
        kick = np.sin(2 * math.pi * 50.0 * pos * (1.0 + 2.0 * np.exp(-pos * 30))) * np.exp(-pos * 9)
        step = (np.floor(t / (beat / 2)) % len(self.BASS)).astype(int)
        bass = 0.45 * np.sin(2 * math.pi * np.take(self.BASS, step) * t) \
            * np.exp(-np.mod(t, beat / 2) * 3)
        off = np.mod(t + beat / 2, beat)                        # off-beat hi-hat
        hat = 0.25 * self.rng.standard_normal(len(t)) * np.exp(-off * 45)
        hat = np.diff(np.concatenate([[0.0], hat]))             # keeps it in the treble
        swell = 0.5 + 0.5 * np.sin(2 * math.pi * t / (beat * 8))
        pad = 0.12 * swell * sum(np.sin(2 * math.pi * f * t) for f in (440.0, 554.4, 659.3, 1318.5))
        return (0.6 * kick + bass + hat + pad).astype(np.float32) * 0.5

    def read(self, n, now=None):
        now = time.time() if now is None else now
        t = now - (np.arange(n)[::-1] / self.samplerate)
        return self.signal(t)

    def close(self):
        pass


class SoundDetector:
    """Is music actually arriving? True once the sound has been above a
    whisper recently; False after `hold_s` of silence. This is how Equalize
    knows AirPlay is playing -- a paused stream is pure digital silence."""

    def __init__(self, threshold_db=-60.0, hold_s=3.0):
        self.threshold = 10 ** (threshold_db / 20.0)
        self.hold_s = hold_s
        self.last_loud = 0.0

    def update(self, samples, now=None):
        now = time.time() if now is None else now
        rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64)))) if len(samples) else 0.0
        if rms > self.threshold:
            self.last_loud = now
        return (now - self.last_loud) < self.hold_s
