"""Channel art drawn in code (no image model on the free tier): avatar + banner.

    python katha/branding.py <out_dir>

Banner is 2560x1440; YouTube only shows the centre 1546x423 on every device, so
everything that matters sits inside that box.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

F = Path(__file__).resolve().parent / "fonts"
SAFFRON, GOLD, INK = (255, 176, 0), (232, 185, 92), (14, 10, 8)


def font(name, size, wght=None):
    f = ImageFont.truetype(str(F / name), size)
    if wght:
        try:
            f.set_variation_by_axes([wght])
        except Exception:
            pass
    return f


def backdrop(w, h, glow=(90, 46, 6)):
    """Near-black with a warm radial glow in the middle, like the Shorts' graded backdrop."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)
    t = np.clip(1 - d, 0, 1)[..., None] ** 1.6
    img = np.array(INK, np.float32) * (1 - t) + np.array(glow, np.float32) * t
    return Image.fromarray(img.astype(np.uint8))


def centred(draw, cx, y, text, f, fill, stroke=0, stroke_fill=INK):
    w = draw.textlength(text, font=f)
    draw.text((cx - w / 2, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def avatar(out, mark="?!", ring=SAFFRON, size=800):
    img = backdrop(size, size)
    d = ImageDraw.Draw(img)
    pad = 46
    d.ellipse([pad, pad, size - pad, size - pad], outline=ring, width=26)
    f = font("Mukta-ExtraBold.ttf", 430)
    box = d.textbbox((0, 0), mark, font=f)
    x = (size - (box[2] - box[0])) / 2 - box[0]
    y = (size - (box[3] - box[1])) / 2 - box[1]
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((x, y), mark, font=f, fill=SAFFRON + (200,))
    img.paste(glow.filter(ImageFilter.GaussianBlur(22)), (0, 0), glow.filter(ImageFilter.GaussianBlur(22)))
    d.text((x, y), mark, font=f, fill=(255, 236, 200))
    img.save(out)


def banner(out, title, tagline, footer):
    """footer: a string, or [(text, font_file, wght), ...] so each script gets a font that has its glyphs."""
    W, H = 2560, 1440
    img = backdrop(W, H)
    d = ImageDraw.Draw(img)
    cx, top = W // 2, (H - 423) // 2
    # thin gold rules framing the text block inside the safe area
    d.line([(cx - 700, top + 18), (cx + 700, top + 18)], fill=GOLD, width=3)
    d.line([(cx - 700, top + 418), (cx + 700, top + 418)], fill=GOLD, width=3)
    centred(d, cx, top + 40, title, font("Mukta-ExtraBold.ttf", 170), SAFFRON)
    centred(d, cx, top + 245, tagline, font("Mukta-Bold.ttf", 64), (255, 240, 220))
    parts = [(footer, "Mukta-Bold.ttf", None)] if isinstance(footer, str) else footer
    fs = [font(fn, 46, w) for _, fn, w in parts]
    gap = 44
    widths = [d.textlength(t, font=f) for (t, _, _), f in zip(parts, fs)]
    x = cx - (sum(widths) + gap * (len(parts) - 1)) / 2
    for (t, _, _), f, w in zip(parts, fs, widths):
        d.text((x, top + 336), t, font=f, fill=GOLD); x += w + gap
    img.save(out)


def fb_cover(out, title, tagline, left=(), right=()):
    """Facebook Page cover, 1640x624. The new Page layout centres the profile picture over the
    cover's lower middle (it covered half of a centred banner), and the phone view crops ~12% off
    each side. So: title and tagline in the top 45%, side items flanking the picture, all inside
    the middle 75%."""
    W, H = 1640, 624
    img = backdrop(W, H)
    d = ImageDraw.Draw(img)
    centred(d, W // 2, 40, title, font("Mukta-ExtraBold.ttf", 120), SAFFRON)
    centred(d, W // 2, 190, tagline, font("Mukta-Bold.ttf", 46), (255, 240, 220))
    d.line([(W // 2 - 430, 268), (W // 2 + 430, 268)], fill=GOLD, width=3)
    for items, x0, x1 in ((left, 230, 650), (right, 990, 1410)):
        for i, (t, fn, w) in enumerate(items):
            f = font(fn, 40, w)
            row, col = divmod(i, 2)
            cx = x0 + (x1 - x0) * (0.25 + 0.5 * col)
            centred(d, cx, 330 + row * 78, t, f, GOLD)
    img.save(out)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    avatar(out / "strange_avatar.png")
    banner(out / "strange_banner.png", "STRANGE BUT TRUE",
           "Famous places. The true stories behind them.", "A new true story every day")
    banner(out / "ajab_banner.png", "अजब गजब", "Stories from India, in your language",
           [("తెలుగు", "NotoSansTelugu.ttf", 700), ("हिंदी", "Mukta-Bold.ttf", None), ("ಕನ್ನಡ", "NotoSansKannada.ttf", 700),
            ("தமிழ்", "NotoSansTamil.ttf", 700), ("বাংলা", "NotoSansBengali.ttf", 700), ("मराठी", "Mukta-Bold.ttf", None),
            ("മലയാളം", "NotoSansMalayalam.ttf", 700), ("ગુજરાતી", "NotoSansGujarati.ttf", 700)])
    print("wrote", *sorted(p.name for p in out.glob("*.png")))
