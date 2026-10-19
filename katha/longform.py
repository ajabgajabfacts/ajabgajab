"""Long-form story videos: 7 fact-checked chapters, ~8-10 min, landscape.

    python katha/longform.py --lang hi                       # next collection, render + upload
    python katha/longform.py --lang ta --collection mysteries --no-upload
    python katha/longform.py --lang hi --chapters 2 --no-upload   # quick local test

Each chapter is a deeper retelling (write.write(chapter=True)) through the same
checker, image vet and renderer as the Shorts. The intro only teases the chapter
titles - it may not introduce facts, because nothing checks it against a source.
Description carries YouTube chapter timestamps (watch-time) and every credit.
"""
import argparse, datetime as dt, json, os, random, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ai, bank, media, render, write
from langs import LANGS
from make import MUSIC, MUSIC_OK, upload

LEDGER = HERE / "longform_ledger.json"

# Collections. `pool(lang)` returns candidate stories in preference order; regional
# stories are welcome in any language in long-form (a Tamil viewer will watch 9
# minutes about Konark), but the language's own region goes first.
def _by(kinds=None, keys=None):
    def pool(lang):
        c = [s for s in bank.S if (keys and s["key"] in keys) or (kinds and s["kind"] in kinds)]
        return sorted(c, key=lambda s: (s["lang"] not in (lang,), s["lang"] != "all"))
    return pool

COLLECTIONS = {
    "mysteries": dict(theme="India's most mysterious and unbelievable places", pool=_by(kinds={"wonder", "folk"})),
    "mahabharata": dict(theme="untold stories of the Mahabharata", pool=_by(keys={
        "ekalavya", "karna_kavacha", "barbarika", "bhishma_vow", "abhimanyu", "ashwatthama", "gandhari", "yaksha_prashna",
        "draupadi_akshaya", "karna_after", "krishna_last_day", "samba_pestle", "ganesha_scribe"})),
    "gods": dict(theme="surprising stories of the gods and their families", pool=_by(keys={
        "ganesha_head", "ganesha_kartikeya_race", "riddhi_siddhi", "kartikeya_wives", "hanuman_sun", "hanuman_son",
        "shiva_ganga_jata", "alakshmi", "garuda_vishnu", "ravana_kailash", "vamana_bali", "samudra_manthan", "parashurama"})),
    "devotion": dict(theme="legends of devotion that moved the gods", pool=_by(keys={
        "gajendra_moksha", "dhruva", "prahlada_narasimha", "prahlad_after", "markandeya", "savitri_satyavan", "nachiketa",
        "sudama", "shabari", "jatayu", "kannappa", "meera", "tukaram", "kanhopatra", "andal", "narsinh_mehta"})),
    "marvels": dict(theme="India's mind-blowing engineering, science and space feats", pool=_by(kinds={"engineering", "space", "science"})),
    "wild": dict(theme="India's most incredible animals and natural wonders", pool=_by(kinds={"animal", "nature"})),
    "legends": dict(theme="real Indian legends - kings, queens, saints and sportspeople", pool=_by(kinds={"history", "saint", "sport", "people"})),
    "food": dict(theme="the surprising origins of India's favourite foods", pool=_by(kinds={"food"})),
}
ORDER = ["mysteries", "gods", "marvels", "mahabharata", "wild", "devotion", "legends", "food"]

FRAME = """You write the opening and closing of a {lang_name} YouTube story video for {audience}.
Theme: {theme}. The chapters, in order (their {lang_name} titles):
{chapters}

Write in natural spoken {lang_name}, native script. Do NOT state any fact that is not in a chapter title:
the intro TEASES, it never informs.
Return JSON:
{{"title": "{lang_name} video title, max 70 chars, curiosity-driven, true to the chapters",
 "intro": ["3-4 short spoken sentences, 35-55 words total: a gripping hook for the whole video, teasing 2-3 chapters"],
 "outro": ["2 sentences: ask which story amazed them most (comment), then a short line to subscribe for more stories"],
 "thumb_text": "2-4 punchy words in {lang_name} for the thumbnail",
 "kicker": "1-2 word {lang_name} label for the series, like STORIES / MYSTERIES",
 "chapter_word": "the {lang_name} word for 'chapter'",
 "intro_label": "the {lang_name} word for 'introduction'",
 "outro_label": "the {lang_name} word for 'conclusion'",
 "subscribe": "max 3 words in {lang_name}: subscribe",
 "description": "3 lines in {lang_name} describing the video",
 "hashtags": ["6 hashtags without #, mix {lang_name} and English"]}}"""


def ledger():
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []


def pick_collection(lang, force=None):
    if force:
        return force
    n = len([r for r in ledger() if r["lang"] == lang])
    return ORDER[n % len(ORDER)]


def segment(L, sentences, shots, hook, kicker, work, name, cta=None):
    """Narrate + render one landscape segment; returns (mp4, seconds)."""
    text = " ".join(sentences)
    voice = work / f"{name}.wav"
    D = media.narrate(text, voice)
    asr = media.asr(voice, L["whisper"])
    wt = media.word_times(text.split(), asr, D)
    music = MUSIC / random.Random(name).choice(MUSIC_OK)
    job = dict(L=L, sentences=sentences, word_times=wt, hook_text=hook, kicker=kicker, cta=cta,
               shots=shots, voice=voice, music=music if music.exists() else None, duration=D + 0.9, landscape=True)
    seg_dir = work / name; seg_dir.mkdir(exist_ok=True)
    out = render.render(job, work / f"{name}.mp4", seg_dir)
    return out, media.duration(out)


def thumbnail(img, text, L, kicker, out):
    from PIL import Image, ImageDraw
    import numpy as np  # noqa
    W, H = 1280, 720
    im = img.convert("RGB")
    s = max(W / im.width, H / im.height); im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    a = np.array(im).astype(np.float32)
    a = np.clip((a - 128) * 1.15 + 128, 0, 255)
    grad = np.clip(1.0 - np.linspace(0, 1, W)[None, :, None] * 1.4, 0, 1) * 0.75
    a = a * (1 - grad)
    im = Image.fromarray(a.astype("uint8")).convert("RGBA")
    f = render.font(L, 128)
    words = text.split()
    lines = render.wrap(words, f, 760)
    while len(lines) > 3:
        f = render.font(L, f.size - 12); lines = render.wrap(words, f, 760)
    if len(lines) >= 2 and len(lines[-1]) == 1 and len(words) >= 3:   # no orphan word on the last line
        half = (len(words) + 1) // 2
        lines = [words[:half], words[half:]]
        while max(f.getlength(" ".join(l)) for l in lines) > 1180:
            f = render.font(L, f.size - 8)
    d = ImageDraw.Draw(im)
    y = 120
    for i, ln in enumerate(lines):
        d.text((60, y), " ".join(ln), font=f, fill=(255, 176, 0, 255) if i == len(lines) - 1 else (255, 255, 255, 255),
               stroke_width=10, stroke_fill=(0, 0, 0, 255))
        y += int(f.size * 1.25)
    p = render.pill(kicker, render.font(L, 44), render.SAFFRON)
    im.alpha_composite(Image.fromarray(p), (60, 40))
    im.convert("RGB").save(out, "JPEG", quality=90)
    return out


def ts(sec):
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="hi")
    ap.add_argument("--collection")
    ap.add_argument("--chapters", type=int, default=7)
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--out", default=str(HERE / "out"))
    a = ap.parse_args()
    L = LANGS[a.lang]
    cid = pick_collection(a.lang, a.collection)
    col = COLLECTIONS[cid]
    used = {k for r in ledger() if r["lang"] == a.lang for k in r["keys"]}
    cands = [s for s in col["pool"](a.lang) if s["key"] not in used] or col["pool"](a.lang)
    work = Path(a.out) / f"{dt.date.today()}_long_{a.lang}_{cid}"; work.mkdir(parents=True, exist_ok=True)
    print(f"[long] {a.lang} / {cid}: {len(cands)} candidates")

    chapters = []                                    # (entry, script, shots, sources)
    for e in cands:
        if len(chapters) >= a.chapters:
            break
        try:
            sources = media.wiki(e["wiki"])
            if not sources:
                continue
            src = "\n\n".join(f"### {x['title']}\n{x['text']}" for x in sources)
            s, _ = write.write(e, a.lang, L, src, chapter=True)
            story_en = f"{e['key'].replace('_', ' ')} - " + "; ".join(s.get("claims_en", [])[:4])
            shots = media.images(e, s.get("visuals"), story_en, need=8)
            if len(shots) < 4:
                print(f"[long] skip {e['key']}: {len(shots)} images"); continue
            chapters.append((e, s, shots, sources))
            print(f"[long] chapter {len(chapters)}: {e['key']} ({len(' '.join(s['sentences']).split())} words)")
        except Exception as err:
            print(f"[long] skip {e['key']}: {str(err)[:150]}")
    if len(chapters) < min(3, a.chapters):
        raise SystemExit(f"only {len(chapters)} chapters passed")

    fr = ai.json_call(FRAME.format(lang_name=L["name"], audience=L["audience"], theme=col["theme"],
                                   chapters="\n".join(f"{i + 1}. {c[1]['title']}" for i, c in enumerate(chapters))))
    (work / "frame.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
    best = sorted([sh for c in chapters for sh in c[2]], key=lambda x: -x["score"])

    parts, marks, t = [], [], 0.0
    intro, d = segment(L, fr["intro"], [b["img"] for b in best[:4]], fr["thumb_text"], fr["kicker"], work, "s00_intro")
    parts.append(intro); marks.append((0.0, fr.get("intro_label", "Intro"))); t += d
    for i, (e, s, shots, _) in enumerate(chapters, 1):
        kick = f"{fr.get('chapter_word', '')} {i}/{len(chapters)}".strip()
        mp4, d = segment(L, s["sentences"], [x["img"] for x in shots], s["hook_text"], kick, work, f"s{i:02d}_{e['key']}")
        parts.append(mp4); marks.append((t, f"{i}. {s['title']}")); t += d
        print(f"[long] rendered chapter {i} ({d:.0f}s)")
    outro, d = segment(L, fr["outro"], [b["img"] for b in best[4:8]] or [best[0]["img"]], fr["thumb_text"],
                       fr["kicker"], work, "s99_outro", cta=fr.get("subscribe"))
    parts.append(outro); marks.append((t, fr.get("outro_label", "Outro"))); t += d

    lst = work / "parts.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    final = work / "long.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    thumb = thumbnail(best[0]["img"], fr["thumb_text"], L, fr["kicker"], work / "thumb.jpg")
    print(f"[long] {final} {t / 60:.1f} min")

    credit = ["Sources (Wikipedia, CC BY-SA 4.0): " + ", ".join(sorted({x["title"] for c in chapters for x in c[3]})),
              "Images (Wikimedia Commons):"]
    seen = set()
    for c in chapters:
        for sh in c[2]:
            if sh["file"] not in seen:
                seen.add(sh["file"]); credit.append(f"- {sh['file'][5:]} - {sh['artist']} - {sh['license']}")
    tags = [h.lstrip("#").strip() for h in fr.get("hashtags", [])]
    desc = (fr["description"] + "\n\n" + "\n".join(f"{ts(m[0])} {m[1]}" for m in marks) + "\n\n"
            + " ".join("#" + x.replace(" ", "") for x in tags[:6]) + "\n\n" + "\n".join(credit))
    meta = dict(title=fr["title"], description=desc, tags=tags + ["ajab gajab", "stories", L["name"]], lang=a.lang,
                comment=fr["outro"][0])
    (work / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.no_upload:
        return
    cfg = os.environ.get("CHANNEL_CONFIG") or (HERE.parent / "CHANNEL_Ajab_Gajab_Facts_CONFIG.json").read_text()
    vid = upload(final, meta, cfg, thumb=thumb)
    print(f"[upload] https://youtube.com/watch?v={vid}")
    led = ledger()
    led.append(dict(date=str(dt.date.today()), lang=a.lang, collection=cid, keys=[c[0]["key"] for c in chapters],
                    video_id=vid, title=fr["title"], minutes=round(t / 60, 1)))
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
