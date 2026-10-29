"""endcard.py — the channel sign-off: a 2 s like + subscribe overlay plus each channel's own music sting.

Owner, 2026-10-28: every channel should end on a branded like + subscribe moment with its own sound, so the
videos read as one channel's work rather than a template. It plays for 2 s AFTER the last line, over the
held last shot, softly blurred so old captions recede (never covering narration or the closing question), and never as a blank end card: Quizora's full-screen card (removed 2026-07) blanked the reveal and broke the Shorts
loop. Ships 2026-11-03, after the calm-look and long-form reads (see the owner's call that day).

    python endcard.py preview <channel> <video.mp4> <out.mp4> [lang]   # overlay + sting on the last 2 s
    python endcard.py sting <channel> <out.wav>

Motion stays calm (no pop, no punch-zoom; the owner disliked both on 10-23): the card fades up, a touch
dot taps Like, then Subscribe; each button settles to its done state. The taps land on the sting's clicks.
"""
import subprocess, sys, wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
SR = 48000
FPS = 30
DUR = 2.0
LIKE_TAP = 0.7                  # owner 10-28: ask for the like AND the subscribe, shown as taps
TAP = 1.2

# Avatars are the live channel icons; name/tagline are what the card prints.
CHANNELS = {
    "quizora": dict(name="Quizora", tag="A new quiz every day", accent=(46, 230, 192), avatar="brand/avatar_quizora.png"),
    "ajab":    dict(name="अजब गजब", tag=None, accent=(255, 170, 40), avatar="brand/avatar_ajab.png"),
    "wtr":     dict(name="Wait, That's Real?", tag="A new true story every day", accent=(255, 176, 0), avatar="brand/strange_avatar.png"),
    "l3c":     dict(name="Level 3 Challenge", tag="A new puzzle every day", accent=(40, 200, 170), avatar="brand/avatar_l3c.png"),
}


def _font(size, fn="Mukta-ExtraBold.ttf"):
    # RAQM shapes Indic scripts (without it the Hindi i-matra lands after its consonant: "लिए" read wrong, 10-28)
    eng = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
    return ImageFont.truetype(str(FONTS / fn), size, layout_engine=eng)


def _ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def _round_avatar(path, d):
    im = Image.open(HERE / path).convert("RGB").resize((d, d), Image.LANCZOS)
    mask = Image.new("L", (d * 4, d * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, d * 4 - 1, d * 4 - 1], fill=255)
    out = Image.new("RGBA", (d, d))
    out.paste(im, (0, 0), mask.resize((d, d), Image.LANCZOS))
    return out


def _bell(draw, cx, cy, s, fill):
    """A plain bell glyph drawn from shapes (no emoji font, so it renders the same on CI)."""
    draw.pieslice([cx - s, cy - s, cx + s, cy + s * 1.1], 180, 360, fill=fill)
    draw.rectangle([cx - s, cy, cx + s, cy + s * 0.55], fill=fill)
    draw.polygon([(cx - s * 1.25, cy + s * 0.75), (cx + s * 1.25, cy + s * 0.75), (cx + s, cy + s * 0.45), (cx - s, cy + s * 0.45)], fill=fill)
    draw.ellipse([cx - s * 0.3, cy + s * 0.8, cx + s * 0.3, cy + s * 1.25], fill=fill)


def _thumb(draw, cx, cy, s, fill):
    """Thumbs-up drawn from shapes, same reason as the bell."""
    draw.rounded_rectangle([cx - s * 0.95, cy - s * 0.1, cx - s * 0.55, cy + s * 0.9], s * 0.12, fill=fill)       # cuff
    draw.rounded_rectangle([cx - s * 0.45, cy - s * 0.1, cx + s * 0.85, cy + s * 0.9], s * 0.3, fill=fill)        # fist
    draw.polygon([(cx - s * 0.45, cy), (cx - s * 0.1, cy - s * 0.95), (cx + s * 0.2, cy - s * 0.95),
                  (cx + s * 0.15, cy - s * 0.1)], fill=fill)                                                       # thumb


def frames(channel, W=1080, H=1920, tag=None, tag_font=None, name=None, name_font=None):
    """RGBA frames (numpy, H x W x 4) for DUR seconds at FPS."""
    C = CHANNELS[channel]
    tag = tag or C["tag"] or ""
    k = W / 1080
    cw, ch = int(860 * k), int(300 * k)
    cx0 = (W - cw) // 2 - int(40 * k)           # nudged left: Shorts' like/comment column covers the right edge
    cy0 = int(H * 0.42)                          # centre: the held shot behind is blurred, and Shorts' bottom strip stays clear
    av = _round_avatar(C["avatar"], int(150 * k))
    name = name or C["name"]
    f_name = name_font or _font(int(60 * k) if len(name) < 14 else int(50 * k))
    f_tag = tag_font or _font(int(34 * k), "Mukta-Bold.ttf")
    f_btn = _font(int(38 * k))
    bx0, by0, bw, bh = cx0 + int(40 * k), cy0 + ch - int(110 * k), cw - int(80 * k), int(80 * k)
    tx, ty = bx0 + bw * 0.62, by0 + bh * 0.55     # where the touch dot presses

    out = []
    for i in range(int(DUR * FPS)):
        t = i / FPS
        a = _ease(t / 0.3)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        # soft scrim behind the card only, so the last shot stays visible (the loop still reads)
        scrim = Image.new("L", (W, H), 0)
        ImageDraw.Draw(scrim).rounded_rectangle([cx0 - 60, cy0 - 60, cx0 + cw + 60, cy0 + ch + 60], 80, fill=int(120 * a))
        img.paste((0, 0, 0, 255), (0, 0), scrim.filter(ImageFilter.GaussianBlur(50 * k)))

        card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        y = cy0 + int(30 * k * (1 - a))
        d.rounded_rectangle([cx0, y, cx0 + cw, y + ch], int(40 * k), fill=(16, 14, 20, 225), outline=C["accent"] + (255,), width=max(2, int(3 * k)))
        card.alpha_composite(av, (cx0 + int(36 * k), y + int(28 * k)))
        nx = cx0 + int(36 * k) + av.width + int(28 * k)
        d.text((nx, y + int(40 * k)), name, font=f_name, fill=(255, 255, 255, 255))
        d.text((nx, y + int(122 * k)), tag, font=f_tag, fill=(225, 225, 225, 255))

        dy = y - cy0
        by = by0 + dy
        # Like (left third) and Subscribe (rest)
        lw_ = int(bw * 0.32)
        liked = t >= LIKE_TAP
        lfill = C["accent"] + (255,) if liked else (255, 255, 255, 40)
        if LIKE_TAP <= t < LIKE_TAP + 0.12:
            lfill = (255, 255, 255, 110)
        d.rounded_rectangle([bx0, by, bx0 + lw_, by + bh], bh // 2, fill=lfill, outline=(255, 255, 255, 230), width=max(2, int(3 * k)))
        _thumb(d, bx0 + lw_ * 0.30, by + bh * 0.47, int(20 * k), (20, 20, 20, 255) if liked else (255, 255, 255, 255))
        d.text((bx0 + lw_ * 0.47, by + bh / 2), "LIKE", font=f_btn, fill=(20, 20, 20, 255) if liked else (255, 255, 255, 255), anchor="lm")

        sx0 = bx0 + lw_ + int(20 * k)
        sw = bw - lw_ - int(20 * k)
        pressed = t >= TAP
        btn = (64, 64, 70, 255) if pressed else (230, 33, 23, 255)
        if TAP <= t < TAP + 0.12:
            btn = (150, 20, 15, 255)             # the press itself, before it settles
        d.rounded_rectangle([sx0, by, sx0 + sw, by + bh], bh // 2, fill=btn)
        label = "SUBSCRIBED" if pressed else "SUBSCRIBE"
        tw = d.textlength(label, font=f_btn)
        lx = sx0 + (sw - tw) / 2 + (int(24 * k) if pressed else 0)
        d.text((lx, by + bh / 2), label, font=f_btn, fill=(255, 255, 255, 255), anchor="lm")
        if pressed:
            _bell(d, lx - int(32 * k), by + bh / 2 - int(6 * k), int(15 * k), (255, 255, 255, 255))

        # touch dot: glides to Like, taps, glides to Subscribe, taps, fades
        like_pt = (bx0 + lw_ * 0.55, by + bh * 0.55)
        sub_pt = (sx0 + sw * 0.6, by + bh * 0.55)
        start = (W * 0.86, H * 0.86)
        if 0.3 <= t < 1.8:
            if t < 0.82:
                u = _ease((t - 0.3) / 0.38); p0, p1 = start, like_pt
            else:
                u = _ease((t - 0.82) / 0.32); p0, p1 = like_pt, sub_pt
            px, py = p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u
            down = any(tt <= t < tt + 0.12 for tt in (LIKE_TAP, TAP))
            r = int((26 if down else 34) * k)
            fade = 1.0 if t < 1.55 else max(0.0, 1 - (t - 1.55) / 0.25)
            d.ellipse([px - r, py - r, px + r, py + r], fill=(255, 255, 255, int(170 * fade)))
            for tt, (qx, qy) in ((LIKE_TAP, like_pt), (TAP, sub_pt)):
                if tt <= t < tt + 0.4:
                    e = _ease((t - tt) / 0.4)
                    rr = r + int(110 * k * e)
                    d.ellipse([qx - rr, qy - rr, qx + rr, qy + rr], outline=(255, 255, 255, int(150 * (1 - e))), width=max(2, int(4 * k)))

        card.putalpha(Image.fromarray((np.asarray(card.getchannel("A"), np.float32) * a).astype(np.uint8)))
        img.alpha_composite(card)
        out.append(np.asarray(img))
    return out


# ── Sound: each channel's own four-note signature, same every video ─────────────────────────────
MOTIFS = {
    # (midi notes, start times s, timbre). The click lands at TAP on every channel.
    "quizora": ([72, 76, 79, 84], [0.05, 0.25, 0.7, 1.2], "pluck"),       # bright rising major arpeggio
    "ajab":    ([62, 64, 66, 69], [0.05, 0.35, 0.7, 1.2], "bell"),        # Sa Re Ga Pa over a drone
    "wtr":     ([57, 60, 64, 63], [0.05, 0.35, 0.7, 1.2], "piano"),       # minor, ending on a raised question
    "l3c":     ([72, 79, 76, 84], [0.05, 0.2, 0.7, 1.2], "chip"),         # 8-bit "level up" (2026-10-29)
}


def _hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def _note(f, n, timbre):
    t = np.arange(n) / SR
    if timbre == "pluck":
        sig = sum(np.sin(2 * np.pi * f * h * t) / h ** 1.3 for h in range(1, 6)) * np.exp(-t * 7)
    elif timbre == "bell":
        sig = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 4)
               + 0.25 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 8)) * np.exp(-t * 2.2)
    elif timbre == "chip":    # soft square wave, a game's level-up blip
        sq = np.sign(np.sin(2 * np.pi * f * t)) * 0.5 + 0.5 * np.sin(2 * np.pi * f * t)
        sig = sq * np.exp(-t * 6) * 0.6
    else:   # soft piano
        sig = sum(np.sin(2 * np.pi * f * h * t * (1 + 0.0004 * h * h)) / h ** 1.8 for h in range(1, 7)) * np.exp(-t * 3)
    a = int(0.006 * SR)
    sig[:a] *= np.linspace(0, 1, a)
    return sig


def sting(channel, seconds=DUR):
    n = int(seconds * SR) + int(1.2 * SR)      # let the last note ring past the cut; trimmed with a fade
    mix = np.zeros(n)
    notes, starts, timbre = MOTIFS[channel]
    for m, s in zip(notes, starts):
        i = int(s * SR)
        x = _note(_hz(m), n - i, timbre)
        mix[i:] += x * (0.9 if s >= TAP else 0.6)
    if channel == "ajab":                       # quiet tanpura-style drone on Sa and Pa
        t = np.arange(n) / SR
        mix += 0.08 * (np.sin(2 * np.pi * _hz(50) * t) + 0.6 * np.sin(2 * np.pi * _hz(57) * t)) * np.minimum(1, t / 0.3)
    # the taps: short filtered clicks
    click = np.random.default_rng(7).standard_normal(int(0.012 * SR)) * np.exp(-np.linspace(0, 9, int(0.012 * SR)))
    for tt in (LIKE_TAP, TAP):
        i = int(tt * SR)
        mix[i:i + len(click)] += 0.35 * np.convolve(click, np.ones(6) / 6, "same")
    # small room: a few decaying echoes
    wet = np.zeros_like(mix)
    for dly, g in ((0.031, 0.35), (0.053, 0.27), (0.089, 0.2), (0.137, 0.14)):
        j = int(dly * SR)
        wet[j:] += mix[:-j] * g
    mix = mix + wet
    mix = mix[:int(seconds * SR)]
    f = int(0.25 * SR)
    mix[-f:] *= np.linspace(1, 0, f)
    return (mix / (np.abs(mix).max() + 1e-9) * 0.8).astype(np.float32)


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())


def held(last_rgb, k=1.0):
    """The held last shot behind the card: blurred and dimmed, as the preview's ffmpeg gblur/eq."""
    im = Image.fromarray(last_rgb).filter(ImageFilter.GaussianBlur(14 * k))
    return (np.asarray(im, np.float32) * 0.82).astype(np.uint8)


def over(base_rgb, rgba):
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (base_rgb.astype(np.float32) * (1 - a) + rgba[..., :3].astype(np.float32) * a).astype(np.uint8)


def preview(channel, video, out, lang=None):
    """Hold the last frame for DUR more seconds and play the sign-off over it (katha does this inside render)."""
    return append(channel, video, out, lang)


def append(channel, video, out, lang=None):
    """Post-process a finished render: hold its last frame DUR s, blurred, with the card and sting over it.
    Quizora's pipelines use this. The original audio fades over its last 0.3 s so the bed never cuts dead."""
    import json, tempfile
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                       "stream=width,height:format=duration", "-of", "json", str(video)],
                                      capture_output=True, text=True, check=True).stdout)
    W, H = probe["streams"][0]["width"], probe["streams"][0]["height"]
    D = float(probe["format"]["duration"])
    tag, tf = None, None
    if channel == "ajab" and lang:
        sys.path.insert(0, str(HERE))
        from langs import LANGS
        L = LANGS[lang]
        tag, tf = L["sub"], _font(int(34 * W / 1080), L["font"])
        name, nf = L["brand"], _font(int(60 * W / 1080), L["font"])
    else:
        name = nf = None
    tmp = Path(tempfile.mkdtemp())
    for i, fr in enumerate(frames(channel, W, H, tag, tf, name, nf)):
        Image.fromarray(fr).save(tmp / f"f{i:03d}.png")
    write_wav(tmp / "sting.wav", sting(channel))
    t0 = D
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-framerate", str(FPS), "-i", str(tmp / "f%03d.png"),
                    "-i", str(tmp / "sting.wav"), "-filter_complex",
                    f"[0:v]tpad=stop_mode=clone:stop_duration={DUR},gblur=sigma=14:enable='gte(t,{t0})',eq=brightness=-0.12:enable='gte(t,{t0})'[base];[1:v]setpts=PTS+{t0}/TB[o];[base][o]overlay=0:0:eof_action=pass[v];"
                    f"[0:a]afade=t=out:st={max(0.0, D - 0.3):.3f}:d=0.3,apad=pad_dur={DUR}[b];[2:a]adelay={int(t0 * 1000)}|{int(t0 * 1000)}[s];"
                    f"[b][s]amix=inputs=2:duration=longest:normalize=0[a]",
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out)],
                   check=True)
    return out


if __name__ == "__main__":
    if sys.argv[1] == "sting":
        write_wav(sys.argv[3], sting(sys.argv[2]))
    elif sys.argv[1] == "preview":
        preview(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None)
    else:
        raise SystemExit(__doc__)
