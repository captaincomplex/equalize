"""
spectrum.py -- turn a slice of sound into bar heights.

Pure numpy, no hardware, so it can be tested on any machine
(see tests/test_spectrum.py).

The chain, once per frame:

    samples --> window --> FFT --> group into bands --> decibels
            --> automatic gain --> 0..1 per bar --> BarSmoother (gravity, peaks)

An FFT (Fast Fourier Transform) splits a slice of sound into how much energy
there is at each frequency. Bands are spaced logarithmically -- each bar covers
the same *musical* width (roughly the same number of notes), which is how ears
hear pitch. Evenly spaced bands would give almost every bar to the treble.
"""

import numpy as np

FMIN = 50.0          # Hz. Below this is felt more than heard; few speakers play it.
FMAX = 16000.0       # Hz. Above this there is little musical energy.
TILT_DB_PER_OCTAVE = 1.5   # music has more bass energy than treble; tilt
                           # the treble up so the right-hand bars get a look in.
MIN_REF_DB = -40.0   # automatic gain never boosts beyond this (see Analyzer)


def band_bins(samplerate, fft_size, n_bars, fmin=FMIN, fmax=FMAX):
    """Return (starts, ends, centres_hz) for n_bars log-spaced bands.

    starts/ends are FFT bin indices, end exclusive. Every band gets at least
    one bin, and bands never overlap, even at the bass end where one FFT bin
    is wider than a band would ideally be.
    """
    nyquist = samplerate / 2.0
    fmax = min(fmax, nyquist * 0.95)
    edges_hz = np.geomspace(fmin, fmax, n_bars + 1)
    bin_hz = samplerate / fft_size
    edges = np.round(edges_hz / bin_hz).astype(int)
    edges[0] = max(1, edges[0])                  # skip bin 0 (DC offset)
    for i in range(1, len(edges)):               # force strictly increasing
        edges[i] = max(edges[i], edges[i - 1] + 1)
    last_bin = fft_size // 2                     # rfft gives fft_size//2 + 1 bins
    if edges[-1] > last_bin:
        raise ValueError("too many bars for this FFT size")
    starts, ends = edges[:-1], edges[1:]
    centres = np.sqrt(np.maximum(starts, 1) * ends) * bin_hz
    return starts, ends, centres


class Analyzer:
    """Samples in, one level per bar out (each 0.0 .. 1.0).

    Automatic gain: the loudest band seen recently is the "reference", and a
    band that loud fills the panel. The reference sinks slowly when the music
    goes quiet, so a quiet song still moves the bars -- but never below
    MIN_REF_DB, so a fade-out's last whisper isn't magnified into dancing bars.

    sensitivity (1-100) sets how many decibels below the reference still show
    as a lit bar. Higher = taller, busier bars.
    """

    def __init__(self, samplerate, n_bars, fft_size=2048):
        self.samplerate = samplerate
        self.n_bars = n_bars
        self.fft_size = fft_size
        self.window = np.hanning(fft_size).astype(np.float32)
        self.starts, self.ends, self.centres = band_bins(samplerate, fft_size, n_bars)
        self.tilt = TILT_DB_PER_OCTAVE * np.log2(self.centres / self.centres[0])
        # A full-scale sine through this window and FFT reads 0 dB.
        self.norm = (np.sum(self.window) / 2.0) ** 2
        self.ref_db = MIN_REF_DB
        self.ref_fall_db_per_s = 4.0

    def process(self, samples, sensitivity=50, dt=1 / 40):
        x = np.asarray(samples, dtype=np.float32)
        if len(x) < self.fft_size:
            x = np.concatenate([np.zeros(self.fft_size - len(x), np.float32), x])
        x = x[-self.fft_size:]
        x = x - np.mean(x)                                   # remove DC offset
        power = np.abs(np.fft.rfft(x * self.window)) ** 2 / self.norm
        csum = np.concatenate([[0.0], np.cumsum(power)])
        band_power = csum[self.ends] - csum[self.starts]     # energy per band
        db = 10.0 * np.log10(band_power + 1e-12) + self.tilt

        # Automatic gain: jump up instantly to a louder band, sink slowly.
        self.ref_db = max(float(np.max(db)),
                          self.ref_db - self.ref_fall_db_per_s * dt,
                          MIN_REF_DB)
        range_db = 20.0 + 0.5 * max(1, min(100, sensitivity))   # 20..70 dB
        levels = (db - (self.ref_db - range_db)) / range_db
        return np.clip(levels, 0.0, 1.0)


class BarSmoother:
    """Makes the bars move like a hi-fi's: shoot up, fall back under gravity.

    Raw FFT levels flicker from frame to frame. Rising is almost instant (so
    a drum hit lands on the beat); falling is at a steady rate, which reads as
    motion rather than noise. Peak caps hang briefly at the highest point,
    then drop.
    """

    def __init__(self, n_bars, fall_per_s=1.6, peak_hold_s=0.45, peak_fall_per_s=0.9):
        self.levels = np.zeros(n_bars)
        self.peaks = np.zeros(n_bars)
        self.peak_age = np.zeros(n_bars)
        self.fall_per_s = fall_per_s
        self.peak_hold_s = peak_hold_s
        self.peak_fall_per_s = peak_fall_per_s

    def update(self, target, dt):
        target = np.asarray(target, dtype=float)
        rising = target > self.levels
        fallen = np.maximum(target, self.levels - self.fall_per_s * dt)
        self.levels = np.where(rising, self.levels + 0.7 * (target - self.levels), fallen)

        new_peak = self.levels >= self.peaks
        self.peak_age = np.where(new_peak, 0.0, self.peak_age + dt)
        dropping = self.peak_age > self.peak_hold_s
        self.peaks = np.where(
            new_peak, self.levels,
            np.where(dropping, np.maximum(self.levels, self.peaks - self.peak_fall_per_s * dt),
                     self.peaks))
        return self.levels, self.peaks
