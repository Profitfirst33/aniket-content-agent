"""Make a soft explainer bed (pad + pluck + kick + hat) with no samples, so there is nothing to license.

Usage: python make_music.py <out.wav> <seconds> [bpm]
The bed is mixed under the voice later with ffmpeg sidechain ducking.
"""
import sys
import wave

import numpy as np

out, secs = sys.argv[1], float(sys.argv[2])
bpm = float(sys.argv[3]) if len(sys.argv) > 3 else 92
SR = 48000
n = int(secs * SR)
t = np.arange(n) / SR
beat = 60 / bpm
bar = 4 * beat

# Am - F - C - G, midi notes
CHORDS = [[57, 60, 64], [53, 57, 60], [48, 55, 60], [55, 59, 62]]
hz = lambda m: 440 * 2 ** ((m - 69) / 12)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # one-pole; fine for a 2-3 min bed
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


pad = np.zeros(n)
pluck = np.zeros(n)
kick = np.zeros(n)
hat = np.zeros(n)
rng = np.random.default_rng(7)

n_bars = int(np.ceil(secs / bar))
for b in range(n_bars):
    chord = CHORDS[b % 4]
    s0 = int(b * bar * SR)
    s1 = min(n, int((b + 1) * bar * SR) + int(0.4 * SR))
    tt = np.arange(s1 - s0) / SR
    env = np.minimum(1, tt / 0.6) * np.minimum(1, np.maximum(0, (bar + 0.4 - tt) / 0.5))
    for m in chord:
        for det in (-0.08, 0.08):
            f = hz(m) * 2 ** (det / 12)
            pad[s0:s1] += env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * 0.06
    # pluck arpeggio on 8th notes, an octave up
    arp = [chord[0], chord[1], chord[2], chord[1] + 12, chord[2], chord[1], chord[0] + 12, chord[2]]
    for k, m in enumerate(arp):
        p0 = s0 + int(k * beat / 2 * SR)
        p1 = min(n, p0 + int(0.5 * SR))
        if p0 >= n:
            break
        pt = np.arange(p1 - p0) / SR
        f = hz(m + 12)
        pluck[p0:p1] += np.exp(-pt * 9) * (np.sin(2 * np.pi * f * pt) + 0.2 * np.sin(6 * np.pi * f * pt)) * 0.05
    for k in range(4):
        q0 = s0 + int(k * beat * SR)
        if q0 >= n:
            break
        if k in (0, 2):  # soft kick
            q1 = min(n, q0 + int(0.35 * SR))
            qt = np.arange(q1 - q0) / SR
            freq = 45 + 75 * np.exp(-qt * 30)
            kick[q0:q1] += np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-qt * 9) * 0.35
        h0 = q0 + int(beat / 2 * SR)  # off-beat hat
        h1 = min(n, h0 + int(0.05 * SR))
        if h0 < n:
            ht = np.arange(h1 - h0) / SR
            hat[h0:h1] += rng.standard_normal(h1 - h0) * np.exp(-ht * 80) * 0.025

pad = lowpass(pad, 1800)
hat = hat - lowpass(hat, 6000)
mix = pad + pluck + kick + hat
fade = np.minimum(1, t / 2.0) * np.minimum(1, np.maximum(0, (secs - t) / 3.0))
mix *= fade
mix /= np.max(np.abs(mix)) + 1e-9
mix *= 0.7
# a little stereo width: right channel 12 ms late
d = int(0.012 * SR)
stereo = np.stack([mix, np.roll(mix, d)], axis=1)
pcm = (stereo * 32767).astype("<i2")
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f"wrote {out} {secs:.1f}s @ {bpm:.0f} bpm")
