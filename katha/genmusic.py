"""genmusic.py — background music we synthesise ourselves, so no copyright match anywhere.

Built 2026-10-23 for the Facebook Reels cross-post: the YouTube Audio Library's
licence is unclear outside YouTube, and a Rights Manager match on Facebook would
block monetisation. Every note here comes from this file, so the same render is
safe on both platforms.

The sound is the owner-approved sample (soft lo-fi: warm pad, bass, plucked
8th-note arpeggio, light kick/snare/hat from bar 3). Each video varies key,
tempo and chord order from a seed, so the channel doesn't loop one track.

Story moods (2026-10-23, for Ajab Gajab and Strange But True): mystery, epic,
devotional, wonder. Same engine, different scales, voices and rhythm.

    python genmusic.py out.wav [seconds] [seed]
    python genmusic.py --samples <dir>      # one sample per mood, to listen to
"""
import random, sys, wave
from pathlib import Path
import numpy as np

SR = 48000

# I-V-vi-IV first: it is the approved sample's progression. Voicings are MIDI
# notes in C; the whole set is transposed per video.
PROGRESSIONS = [
    [[48, 55, 64, 67], [43, 55, 62, 67], [45, 57, 64, 69], [41, 57, 60, 65]],   # C G Am F
    [[45, 57, 64, 69], [41, 57, 60, 65], [48, 55, 64, 67], [43, 55, 62, 67]],   # Am F C G
    [[48, 55, 64, 67], [45, 57, 64, 69], [41, 57, 60, 65], [43, 55, 62, 67]],   # C Am F G
    [[41, 57, 60, 65], [43, 55, 62, 67], [45, 57, 64, 69], [48, 55, 64, 67]],   # F G Am C
]


def _hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def _env(n, a, r):
    e = np.ones(n)
    a, r = int(a * SR), int(r * SR)
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    return e


def generate(out_path, seconds, seed=0, sample=False, mood="quiz"):
    """Write a stereo 48 kHz WAV at least `seconds` long. sample=True reproduces the approved sample exactly.
    mood: "quiz" (the approved lo-fi) or one of MOODS for the story channels."""
    if mood != "quiz":
        return _story(out_path, seconds, seed, mood)
    pick = random.Random(seed)
    bpm = 92 if sample else pick.choice([86, 88, 90, 92, 94, 96])
    shift = 0 if sample else pick.choice([-3, -2, 0, 2, 3, 5])
    prog = PROGRESSIONS[0] if sample else pick.choice(PROGRESSIONS)
    rng = np.random.default_rng(7 if sample else seed)

    beat = 60 / bpm
    bars = max(2, int(np.ceil(seconds / (4 * beat))) + 1)
    out = np.zeros((int(bars * 4 * beat * SR), 2), np.float32)

    def add(sig, start, pan=0.5):
        i = int(start * SR); j = min(len(out), i + len(sig)); s = sig[:j - i]
        out[i:j, 0] += s * (1 - pan); out[i:j, 1] += s * pan

    for b in range(bars):
        ch = [m + shift for m in prog[b % 4]]
        st, n = b * 4 * beat, int(4 * beat * SR)
        t = np.arange(n) / SR
        for k, m in enumerate(ch):                       # pad: a few soft harmonics, slightly detuned
            f = _hz(m)
            s = sum(np.sin(2 * np.pi * f * h * t * (1 + 0.002 * (-1) ** h)) / h ** 1.8 for h in range(1, 5))
            add(0.05 * s * _env(n, 0.6, 1.0), st, pan=0.3 + 0.4 * (k % 2))
        f = _hz(ch[0] - 12); tb = np.arange(int(beat * 2 * SR)) / SR
        for q in (0, 2):                                 # bass on 1 and 3
            add(0.16 * np.sin(2 * np.pi * f * tb) * np.exp(-tb * 2.2), st + q * beat)
        arp = [ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 12]
        tp = np.arange(int(0.5 * SR)) / SR
        for e8 in range(8):                              # plucked 8th-note arpeggio
            f = _hz(arp[e8 % 4] + (12 if e8 == 6 and b % 2 else 0))
            s = (np.sin(2 * np.pi * f * tp) + 0.3 * np.sin(4 * np.pi * f * tp)) * np.exp(-tp * 7)
            add(0.06 * s, st + e8 * beat / 2, pan=0.25 if e8 % 2 else 0.75)
        if b >= 2:                                       # light drums from bar 3
            tk = np.arange(int(0.25 * SR)) / SR
            for q in range(4):
                if q in (0, 2):
                    add(0.22 * np.sin(2 * np.pi * (55 + 90 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 12), st + q * beat)
                else:
                    sn = rng.standard_normal(int(0.18 * SR))
                    add(0.035 * sn * np.exp(-np.arange(len(sn)) / SR * 25), st + q * beat)
                for h in (0, 0.5):
                    hh = np.diff(rng.standard_normal(int(0.05 * SR)), prepend=0)
                    add(0.02 * hh * np.exp(-np.arange(len(hh)) / SR * 80), st + (q + h) * beat, pan=0.6)

    out = out[:int(max(seconds, 3) * SR)]
    fi, fo = int(1.5 * SR), min(int(3 * SR), len(out) // 3)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    out /= np.abs(out).max() / 0.8
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return Path(out_path)


# ── Story moods ──────────────────────────────────────────────────────────────
# Each mood: tempo range, chord roots (semitones from the key) with a scale for
# the melody, and which voices play. All synthesis, so nothing to copyright-match.
MOODS = {
    "mystery":    dict(bpm=(68, 76), keys=(-5, -3, -2, 0), roots=[0, -4, -7, -2], minor=True,
                       scale=[0, 2, 3, 7, 8], voices=("drone", "bell", "tick", "pad")),
    "epic":       dict(bpm=(78, 86), keys=(-5, -3, -2), roots=[0, -4, 3, -2], minor=True,
                       scale=[0, 2, 3, 5, 7], voices=("strings", "taiko", "pad", "bass")),
    "devotional": dict(bpm=(70, 80), keys=(-3, -2, 0, 2), roots=[0, 0, 5, 7], minor=False,
                       scale=[0, 1, 4, 5, 7, 8, 11], voices=("tanpura", "sitar", "tabla")),   # Bhairav-like
    "wonder":     dict(bpm=(84, 92), keys=(0, 2, 5, 7), roots=[0, 7, 9, 5], minor=False,
                       scale=[0, 2, 4, 7, 9], voices=("pad", "bell", "bass", "shaker")),
}


def _story(out_path, seconds, seed, mood):
    M = MOODS[mood]
    pick = random.Random(f"{mood}{seed}")
    rng = np.random.default_rng(seed)
    bpm = pick.randint(*M["bpm"]); key = 48 + pick.choice(M["keys"])
    beat = 60 / bpm
    bars = max(2, int(np.ceil(seconds / (4 * beat))) + 1)
    out = np.zeros((int(bars * 4 * beat * SR), 2), np.float32)

    def add(sig, start, pan=0.5):
        i = int(start * SR); j = min(len(out), i + len(sig)); s = sig[:j - i]
        if j > i:
            out[i:j, 0] += s * (1 - pan); out[i:j, 1] += s * pan

    def tone(f, n, harm=4, decay=None, det=0.002):
        t = np.arange(n) / SR
        s = sum(np.sin(2 * np.pi * f * h * t * (1 + det * (-1) ** h)) / h ** 1.6 for h in range(1, harm + 1))
        return s * (np.exp(-t * decay) if decay else 1)

    third = 3 if M["minor"] else 4
    n_bar = int(4 * beat * SR)
    melody_prev = 0
    for b in range(bars):
        root = key + M["roots"][b % len(M["roots"])]
        st = b * 4 * beat
        chord = [root, root + third + 12, root + 19]
        v = M["voices"]
        if "pad" in v:
            for k, m in enumerate(chord):
                add(0.045 * tone(_hz(m), n_bar) * _env(n_bar, 0.9, 1.2), st, pan=0.3 + 0.4 * (k % 2))
        if "strings" in v:                                   # bowed swell: slow attack, light vibrato
            t = np.arange(n_bar) / SR
            for k, m in enumerate(chord + [root + 24]):
                f = _hz(m) * (1 + 0.003 * np.sin(2 * np.pi * 5.2 * t))
                s = sum(np.sin(2 * np.pi * np.cumsum(f * h) / SR) / h ** 1.3 for h in range(1, 6))
                add(0.04 * s * _env(n_bar, 1.6, 1.0), st, pan=0.2 + 0.2 * k)
        if "drone" in v or "tanpura" in v:                   # sustained root + fifth
            for m in (key - 12, key - 5):
                d = tone(_hz(m), n_bar, harm=7 if "tanpura" in v else 3, det=0.004)
                add((0.05 if "tanpura" in v else 0.06) * d * _env(n_bar, 0.4, 0.4), st, pan=0.5)
            if "tanpura" in v:                                # the plucked Pa-Sa-Sa-Sa cycle
                for q, m in enumerate((key - 5, key, key, key - 12)):
                    add(0.05 * tone(_hz(m + 12), int(1.6 * SR), harm=8, decay=1.4), st + q * beat, pan=0.4)
        if "bass" in v:
            for q in (0, 2):
                add(0.14 * tone(_hz(root - 12), int(2 * beat * SR), harm=2, decay=2.0), st + q * beat)
        if "bell" in v or "sitar" in v:                       # sparse melody from the mood's scale
            steps = (0, 1.5, 2.5) if "bell" in v else (0, 0.5, 1, 2, 2.5, 3, 3.5)
            for q in steps:
                if pick.random() < (0.75 if "bell" in v else 0.6):
                    melody_prev = max(0, min(len(M["scale"]) - 1, melody_prev + pick.choice((-1, 0, 1, 1, 2, -2))))
                    m = key + 12 + M["scale"][melody_prev] + (12 if "bell" in v else 0)
                    if "bell" in v:                           # inharmonic partials = bell
                        n = int(2.2 * SR); t = np.arange(n) / SR
                        s = (np.sin(2 * np.pi * _hz(m) * t) + 0.5 * np.sin(2 * np.pi * _hz(m) * 2.76 * t)
                             + 0.25 * np.sin(2 * np.pi * _hz(m) * 5.4 * t)) * np.exp(-t * 2.2)
                        add(0.05 * s, st + q * beat, pan=pick.uniform(0.25, 0.75))
                    else:                                     # sitar-ish: bright pluck with a small upward bend
                        n = int(0.9 * SR); t = np.arange(n) / SR
                        f = _hz(m) * (1 + 0.015 * (1 - np.exp(-t * 18)))
                        ph = 2 * np.pi * np.cumsum(f) / SR
                        s = sum(np.sin(ph * h) / h ** 0.9 for h in range(1, 9)) * np.exp(-t * 3.2)
                        add(0.04 * s, st + q * beat, pan=0.6)
        if b >= 1:
            if "tick" in v:
                for q in range(8):
                    n = int(0.02 * SR); s = np.diff(rng.standard_normal(n), prepend=0) * np.exp(-np.arange(n) / SR * 300)
                    add(0.05 * s, st + q * beat / 2, pan=0.65)
            if "taiko" in v:                                  # deep hits on 1 and the "and" of 3
                for q in (0, 2.5, 3):
                    n = int(0.6 * SR); t = np.arange(n) / SR
                    s = np.sin(2 * np.pi * (48 + 60 * np.exp(-t * 18)) * t) * np.exp(-t * 6)
                    add((0.3 if q == 0 else 0.18) * s, st + q * beat)
            if "tabla" in v:                                  # tun (open) and na (bright) strokes
                for q, kind in ((0, "dha"), (1, "na"), (1.5, "na"), (2, "tun"), (3, "na"), (3.5, "na")):
                    n = int(0.35 * SR); t = np.arange(n) / SR
                    f0 = 90 if kind in ("dha", "tun") else 330
                    s = np.sin(2 * np.pi * f0 * (1 + 0.25 * np.exp(-t * 25)) * t) * np.exp(-t * (8 if kind != "na" else 18))
                    add((0.16 if kind == "dha" else 0.08) * s, st + q * beat, pan=0.45)
            if "shaker" in v:
                for q in range(8):
                    n = int(0.06 * SR); s = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 60)
                    add(0.012 * np.diff(s, prepend=0), st + q * beat / 2, pan=0.7)

    out = out[:int(max(seconds, 3) * SR)]
    fi, fo = int(1.5 * SR), min(int(3 * SR), len(out) // 3)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    out /= np.abs(out).max() / 0.8
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return Path(out_path)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--samples":
        d = Path(sys.argv[2]); d.mkdir(parents=True, exist_ok=True)
        for m in MOODS:
            print("wrote", generate(d / f"{m}.wav", 30, seed=1, mood=m))
        sys.exit()
    p = generate(sys.argv[1] if len(sys.argv) > 1 else "bed.wav",
                 float(sys.argv[2]) if len(sys.argv) > 2 else 31.3,
                 int(sys.argv[3]) if len(sys.argv) > 3 else 0, sample=len(sys.argv) <= 3)
    print("wrote", p)
