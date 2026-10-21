"""Cinematic vertical renderer (1080x1920, 30 fps).

Look: painted/photographed art in slow Ken Burns motion over a blurred, graded
backdrop (landscape art sits in a gold-framed card), floating embers, vignette,
a punch-in hook title, word-by-word highlighted captions, a pulsing comment CTA,
whoosh on every cut and a music bed ducked under the narration.

Layout keeps clear of the Shorts UI: nothing important above y=140, below
y=1600, or right of x=960 between y=900 and 1700 (the action buttons).
"""
import math, random, subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
SAFFRON = (255, 176, 0)
GOLD = (232, 185, 92)
CARD_CY = 975          # landscape art centre; spans ~400-1550
HOOK_Y, CAP_Y, CTA_Y = 300, 1530, 1405
BRAND_X, BRAND_Y, CAP_X, CAP_W, HOOK_W = 60, 178, 520, 860, 900
LANDSCAPE = False


def set_canvas(landscape):
    """Shorts (1080x1920, clear of the Shorts UI) or long-form (1920x1080)."""
    global W, H, CARD_CY, HOOK_Y, CAP_Y, CTA_Y, BRAND_X, BRAND_Y, CAP_X, CAP_W, HOOK_W, LANDSCAPE
    LANDSCAPE = landscape
    if landscape:
        W, H = 1920, 1080
        HOOK_Y, CAP_Y, CTA_Y = 200, 945, 830
        BRAND_X, BRAND_Y, CAP_X, CAP_W, HOOK_W = 70, 70, 960, 1500, 1600
    else:
        W, H = 1080, 1920
        CARD_CY = 975
        HOOK_Y, CAP_Y, CTA_Y = 300, 1530, 1405
        BRAND_X, BRAND_Y, CAP_X, CAP_W, HOOK_W = 60, 178, 520, 860, 900
FONTS = Path(__file__).parent / "fonts"


# ── text ────────────────────────────────────────────────────────────────────
def font(L, size):
    f = ImageFont.truetype(str(FONTS / L["font"]), size, layout_engine=ImageFont.Layout.RAQM)
    if L.get("wght"):
        try:
            axes = f.get_variation_axes()
            f.set_variation_by_axes([L["wght"] if a.get("name", b"") in (b"Weight", "Weight") else a["default"] for a in axes])
        except Exception:
            pass
    return f


def wrap(words, f, maxw):
    lines, cur = [], []
    for w in words:
        t = " ".join(cur + [w])
        if cur and f.getlength(t) > maxw:
            lines.append(cur); cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def text_rgba(words, f, maxw, color=(255, 255, 255), hi=None, hi_color=SAFFRON, stroke=9,
              glow=None, line_colors=None, align="center"):
    """RGBA image of wrapped words; word index `hi` drawn in hi_color."""
    lines = wrap(words, f, maxw)
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * 1.08)
    sp = f.getlength(" ")
    widths = [sum(f.getlength(w) for w in ln) + sp * (len(ln) - 1) for ln in lines]
    pad = stroke + 30
    iw, ih = int(max(widths)) + 2 * pad, lh * len(lines) + 2 * pad
    im = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = 0
    for li, ln in enumerate(lines):
        x = pad + ((iw - 2 * pad - widths[li]) / 2 if align == "center" else 0)
        y = pad + li * lh
        for w in ln:
            c = hi_color if k == hi else (line_colors[li] if line_colors else color)
            d.text((x, y), w, font=f, fill=c + (255,), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
            x += f.getlength(w) + sp; k += 1
    if glow:
        a = im.split()[3].filter(ImageFilter.GaussianBlur(18))
        g = Image.new("RGBA", im.size, glow + (0,)); g.putalpha(a.point(lambda v: int(v * 0.85)))
        g.alpha_composite(im); im = g
    return np.array(im)


def pill(text, f, bg, fg=(20, 12, 0), padx=34, pady=14):
    l, t, r, b = f.getbbox(text)
    w, h = int(r - l) + 2 * padx, int(b - t) + 2 * pady
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=bg + (240,))
    d.text((padx - l, pady - t), text, font=f, fill=fg + (255,))
    return np.array(im)


def blit(frame, rgba, cx, cy, alpha=1.0, scale=1.0):
    if scale != 1.0:
        rgba = cv2.resize(rgba, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    h, w = rgba.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    src = rgba[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    a = (src[:, :, 3:4].astype(np.float32) / 255.0) * alpha
    roi = frame[fy0:fy1, fx0:fx1].astype(np.float32)
    frame[fy0:fy1, fx0:fx1] = (roi * (1 - a) + src[:, :, :3].astype(np.float32) * a).astype(np.uint8)


# ── images ──────────────────────────────────────────────────────────────────
def grade(rgb):
    x = rgb.astype(np.float32) / 255.0
    x = np.clip((x - 0.5) * 1.12 + 0.5, 0, 1)                          # contrast
    hsv = cv2.cvtColor((x * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.18, 0, 255)                # saturation
    x = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
    x[:, :, 0] *= 1.04; x[:, :, 2] *= 0.95                             # warm
    return np.clip(x, 0, 255).astype(np.uint8)


def cover(rgb, w, h, extra=1.0):
    ih, iw = rgb.shape[:2]
    s = max(w / iw, h / ih) * extra
    return cv2.resize(rgb, (int(iw * s + 1), int(ih * s + 1)), interpolation=cv2.INTER_AREA)


class Shot:
    """One image prepared for motion. mode 'cover' fills the screen; 'card' frames landscape art."""

    def __init__(self, pil_img, seed):
        rgb = grade(np.array(pil_img.convert("RGB")))
        ih, iw = rgb.shape[:2]
        self.rng = random.Random(seed)
        if LANDSCAPE:
            self.mode = "cover" if iw / ih >= 1.25 else "pillar"
        else:
            self.mode = "cover" if ih / iw >= 1.15 else "card"
        bg = cover(rgb, W, H, 1.1)
        y0, x0 = (bg.shape[0] - H) // 2, (bg.shape[1] - W) // 2
        bg = cv2.GaussianBlur(bg[y0:y0 + H, x0:x0 + W], (0, 0), 38)
        self.bg = (bg.astype(np.float32) * 0.42).astype(np.uint8)
        if self.mode == "cover":
            self.big = cover(rgb, W, H, 1.0)
        elif self.mode == "pillar":
            # Tall art on a wide canvas: a full-height column with feathered sides.
            ch = H; cw = int(min(W * 0.62, max(W * 0.45, H * iw / ih * 1.25)))
            self.cw, self.ch = cw, ch
            self.big = cover(rgb, cw, ch, 1.0)
            fe = 140
            ramp = np.ones(cw, np.float32)
            ramp[:fe] = np.linspace(0, 1, fe) ** 1.6; ramp[-fe:] = np.linspace(1, 0, fe) ** 1.6
            self.mask = np.repeat(ramp[None, :], ch, axis=0)[:, :, None]
        else:
            # Full-bleed width with feathered top/bottom edges: fills the screen without
            # cropping a landscape painting down to a sliver.
            cw = W; ch = int(min(1150, max(980, W * ih / iw * 1.3)))
            self.cw, self.ch = cw, ch
            self.big = cover(rgb, cw, ch, 1.0)
            fe = 110
            ramp = np.ones(ch, np.float32)
            ramp[:fe] = np.linspace(0, 1, fe) ** 1.6; ramp[-fe:] = np.linspace(1, 0, fe) ** 1.6
            self.mask = np.repeat(ramp[:, None], cw, axis=1)[:, :, None]
        self.zin = self.rng.random() < 0.6
        self.dx, self.dy = self.rng.uniform(-1, 1), self.rng.uniform(-1, 1)

    def _kb(self, src, ow, oh, p):
        z = (1.0 + 0.13 * p) if self.zin else (1.13 - 0.13 * p)
        z *= 1.0 + 0.05 * max(0.0, 1 - p * 8)                           # punch at the cut
        sh, sw = src.shape[:2]
        s = max(ow / sw, oh / sh) * z
        ex, ey = sw * s - ow, sh * s - oh
        tx = -ex / 2 + self.dx * ex / 2 * (p - 0.5)
        ty = -ey / 2 + self.dy * ey / 2 * (p - 0.5)
        M = np.float32([[s, 0, tx], [0, s, ty]])
        return cv2.warpAffine(src, M, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def draw(self, p):
        if self.mode == "cover":
            return self._kb(self.big, W, H, p)
        f = self.bg.copy()
        card = self._kb(self.big, self.cw, self.ch, p)
        if self.mode == "pillar":
            x0 = W // 2 - self.cw // 2
            roi = f[:, x0:x0 + self.cw].astype(np.float32)
            f[:, x0:x0 + self.cw] = (roi * (1 - self.mask) + card * self.mask).astype(np.uint8)
            return f
        y0 = CARD_CY - self.ch // 2
        roi = f[y0:y0 + self.ch].astype(np.float32)
        f[y0:y0 + self.ch] = (roi * (1 - self.mask) + card * self.mask).astype(np.uint8)
        return f


# ── effects ─────────────────────────────────────────────────────────────────
def vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.58)) ** 2)
    v = np.clip(1.15 - 0.55 * d ** 2, 0.35, 1.0)
    # darker bands top and bottom so text always reads
    v *= np.clip(0.55 + yy / 500, 0, 1) * np.clip(0.6 + (H - yy) / 700, 0, 1)
    return v[:, :, None]


class Embers:
    def __init__(self, n=46, seed=7):
        r = random.Random(seed)
        self.p = [[r.uniform(0, W), r.uniform(0, H), r.uniform(18, 60), r.uniform(0, 6.28), r.uniform(6, 22), r.uniform(0.25, 0.8)]
                  for _ in range(n)]
        self.spr = {}

    def sprite(self, s):
        s = int(s)
        if s not in self.spr:
            yy, xx = np.mgrid[0:s * 2, 0:s * 2].astype(np.float32)
            g = np.exp(-(((xx - s) ** 2 + (yy - s) ** 2) / (2 * (s / 3) ** 2)))
            self.spr[s] = (g[:, :, None] * np.array([255, 190, 90], np.float32)[None, None, :])
        return self.spr[s]

    def draw(self, f, t):
        for x, y, v, ph, s, a in self.p:
            yy = (y - v * t) % (H + 100) - 50
            xx = x + 22 * math.sin(ph + t * 0.8)
            sp = self.sprite(s) * a * (0.6 + 0.4 * math.sin(ph * 3 + t * 2.2))
            x0, y0 = int(xx - s), int(yy - s)
            h, w = sp.shape[:2]
            fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
            if fx1 > fx0 and fy1 > fy0:
                roi = f[fy0:fy1, fx0:fx1].astype(np.float32) + sp[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
                f[fy0:fy1, fx0:fx1] = np.clip(roi, 0, 255).astype(np.uint8)


def whooshes(times, total, out_wav, sr=48000):
    rng = np.random.default_rng(3)
    y = np.zeros(int(total * sr) + sr, np.float32)
    n = int(0.45 * sr)
    for t in times:
        noise = rng.standard_normal(n).astype(np.float32)
        # sweep: crude band shaping via running mean of decreasing width, swelling envelope
        env = np.sin(np.linspace(0, np.pi, n)) ** 2
        k = np.convolve(noise, np.ones(24) / 24, mode="same") - np.convolve(noise, np.ones(220) / 220, mode="same")
        s = (k * env * 0.35).astype(np.float32)
        i = max(0, int((t - 0.22) * sr)); y[i:i + n] += s[:len(y) - i]
    y = np.clip(y, -1, 1)
    import wave
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((y * 32767).astype(np.int16).tobytes())


# ── main render ─────────────────────────────────────────────────────────────
def chunks(sentences, maxn=6, maxc=30):
    """Word-index groups that never cross a sentence and break at commas when possible."""
    out, k = [], 0
    for sent in sentences:
        ws = sent.split(); idx = list(range(k, k + len(ws))); k += len(ws)
        n = max(1, -(-len(ws) // maxn))
        while True:                                       # balanced split, respecting the char cap
            size = -(-len(ws) // n)
            parts = [idx[i:i + size] for i in range(0, len(idx), size)]
            if all(sum(len(ws[j - idx[0]]) + 1 for j in pt) <= maxc + 6 for pt in parts) or n >= len(ws):
                break
            n += 1
        out += parts
    return out


def render(job, out_mp4, work):
    """job: L, sentences, word_times (per word over all sentences), sentence_word_counts, hook_text,
    kicker, cta, subscribe, shots (PIL images), voice wav, music path, duration."""
    set_canvas(bool(job.get("landscape")))
    L = job["L"]
    D = job["duration"]
    words = [w for s in job["sentences"] for w in s.split()]
    wt = job["word_times"]
    sent_ranges, k = [], 0
    for s in job["sentences"]:
        n = len(s.split()); sent_ranges.append((k, k + n)); k += n
    s_start = [wt[a][0] for a, b in sent_ranges]
    hook_end = min(max(wt[sent_ranges[0][1] - 1][1], 1.6), 3.4)
    last_start = s_start[-1]

    # Cuts at sentence starts; long sentences split; never shorter than 1.8s.
    cuts = [0.0]
    for t in s_start[1:] + [D]:
        while t - cuts[-1] > 5.2:
            cuts.append(cuts[-1] + 4.2)
        if t - cuts[-1] >= 1.8 and t < D - 0.5:
            cuts.append(t)
    imgs = job["shots"]
    shots = [Shot(imgs[i % len(imgs)], seed=i) for i in range(len(cuts))]
    seg = list(zip(cuts, cuts[1:] + [D]))

    f_brand = font(L, 40); f_kick = font(L, 40); f_hook = font(L, 100); f_cap = font(L, 70 if LANDSCAPE else 84); f_cta = font(L, 48)
    brand = text_rgba([L["brand"]], f_brand, 900, color=(255, 236, 200), stroke=5)
    kicker = pill(job["kicker"], f_kick, SAFFRON)
    hw = job["hook_text"].split()
    hs = 100
    while hs > 60 and len(wrap(hw, f_hook, HOOK_W)) > 2:     # the hook gets two lines, never three
        hs -= 8; f_hook = font(L, hs)
    hook = text_rgba(hw, f_hook, HOOK_W, stroke=12, glow=(255, 120, 0),
                     line_colors=[(255, 255, 255), SAFFRON, (255, 255, 255)])
    cta = pill(job["cta"], f_cta, (255, 255, 255), fg=(10, 10, 10)) if job.get("cta") else None
    sub = None
    if job.get("subscribe"):
        fs = 48                                   # stay clear of the Shorts button column on the right
        while (sub := pill(job["subscribe"], font(L, fs), SAFFRON)).shape[1] > 800 and fs > 32:
            fs -= 4
    sub_start = max(last_start, D - 1.8)         # the subscribe ask owns the last 1.8s, above the comment pill
    caps = chunks(job["sentences"], maxn=9 if LANDSCAPE else 6, maxc=48 if LANDSCAPE else 30)
    cap_of_word = {}
    for ci, c in enumerate(caps):
        for wi in c:
            cap_of_word[wi] = ci
    cap_start = [wt[c[0]][0] for c in caps]
    cache = {}

    vig = vignette(); emb = Embers()
    vid = Path(work) / "video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                           "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(vid)], stdin=subprocess.PIPE)
    nfr = int(D * FPS)
    XF = 0.28
    for fi in range(nfr):
        t = fi / FPS
        si = max(i for i, (a, b) in enumerate(seg) if a <= t)
        a, b = seg[si]
        fr = shots[si].draw((t - a) / max(b - a, 0.1))
        if si + 1 < len(seg) and t > b - XF:                              # crossfade into next shot
            nxt = shots[si + 1].draw(0.0)
            m = (t - (b - XF)) / XF
            fr = cv2.addWeighted(fr, 1 - m, nxt, m, 0)
        fr = (fr.astype(np.float32) * vig).astype(np.uint8)
        emb.draw(fr, t)

        blit(fr, brand, BRAND_X + brand.shape[1] / 2 - 10, BRAND_Y)
        blit(fr, kicker, BRAND_X + brand.shape[1] + kicker.shape[1] / 2, BRAND_Y)

        if t < hook_end + 0.25:
            p = t / 0.22
            sc = 1.35 - 0.35 * min(1, p) if p < 1 else 1.0 + 0.012 * math.sin(t * 9)
            al = min(1.0, p * 1.4) * (1 - max(0.0, (t - hook_end) / 0.25))
            blit(fr, hook, W / 2, HOOK_Y, alpha=al, scale=sc)
        else:
            wi = next((i for i, (s0, s1) in enumerate(wt) if s0 <= t < s1), None)
            if wi is None:
                ci = max([i for i, s in enumerate(cap_start) if s <= t] or [0])
                hi = -1
            else:
                ci = cap_of_word[wi]; hi = caps[ci].index(wi)
            if ci > 0 or cap_start[0] >= hook_end - 0.05 or t >= cap_start[0]:
                key = (ci, hi)
                if key not in cache:
                    cache[key] = text_rgba([words[i] for i in caps[ci]], f_cap, CAP_W, hi=hi)
                pop = min(1.0, (t - cap_start[ci]) / 0.12) if t >= cap_start[ci] else 1.0
                blit(fr, cache[key], CAP_X, CAP_Y, alpha=min(1, 0.4 + pop), scale=0.88 + 0.12 * pop)
        if cta is not None and t >= last_start:
            blit(fr, cta, CAP_X, CTA_Y, scale=1.0 + 0.05 * math.sin((t - last_start) * 7))
        if sub is not None and t >= sub_start:
            p = min(1.0, (t - sub_start) / 0.18)
            blit(fr, sub, CAP_X, CTA_Y - 115, alpha=p, scale=1.3 - 0.3 * p if p < 1 else 1.0 + 0.04 * math.sin(t * 7))
        ff.stdin.write(fr.tobytes())
    ff.stdin.close(); ff.wait()

    sfx = Path(work) / "sfx.wav"
    whooshes(cuts[1:], D, sfx)
    music = job.get("music")
    inputs = ["-i", str(vid), "-i", str(job["voice"]), "-i", str(sfx)]
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        fc = (f"[1:a]apad,asplit=2[v1][v2];[3:a]aresample=48000,volume=0.30,afade=t=in:d=0.8,afade=t=out:st={D - 1.6:.2f}:d=1.6[m];"
              f"[m][v2]sidechaincompress=threshold=0.025:ratio=7:attack=12:release=380[md];"
              f"[v1][md][2:a]amix=inputs=3:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    else:
        fc = "[1:a]apad[v1];[v1][2:a]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{D:.2f}", str(out_mp4)], check=True)
    return out_mp4
