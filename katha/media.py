"""Source text, images, narration and word timings."""
import io, json, os, re, subprocess, sys, wave
from pathlib import Path
import requests
from PIL import Image
import ai

UA = {"User-Agent": "AjabGajabStories/1.0 (https://github.com/ajabgajabfacts/ajabgajab; story research bot)"}
OK_LICENSES = ("public domain", "pd", "cc0", "cc by", "cc-by", "cc by-sa", "cc-by-sa")


def _get_json(url, params, tries=5):
    """Wikimedia returns an empty/HTML body when it rate-limits; back off instead of crashing the run."""
    import time
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=60, params=params)
            if r.status_code == 200:
                return r.json()
        except (requests.RequestException, ValueError):
            pass
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"Wikimedia unavailable: {url}")


# ── Source ──────────────────────────────────────────────────────────────────
def wiki(titles):
    out = []
    for t in titles:
        r = _get_json("https://en.wikipedia.org/w/api.php", dict(
            action="query", format="json", prop="extracts", explaintext=1, redirects=1, titles=t))
        p = list(r["query"]["pages"].values())[0]
        txt = p.get("extract", "")
        if len(txt) > 400:
            out.append(dict(title=p["title"], url="https://en.wikipedia.org/wiki/" + p["title"].replace(" ", "_"),
                            text=re.sub(r"\n==+ (See also|References|External links|Notes|Further reading|Bibliography) ==+[\s\S]*", "", txt)))
    return out


# ── Images ──────────────────────────────────────────────────────────────────
def _strip(html):
    return re.sub(r"<[^>]+>", "", html or "").strip()


def commons(query, limit=14):
    r = _get_json("https://commons.wikimedia.org/w/api.php", dict(
        action="query", format="json", generator="search", gsrnamespace=6, gsrsearch=query, gsrlimit=limit,
        prop="imageinfo", iiprop="url|size|extmetadata|mime", iiurlwidth=1600))
    out = []
    for p in (r.get("query", {}).get("pages", {}) or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata", {})
        lic = _strip(m.get("LicenseShortName", {}).get("value", ""))
        if ii.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if not lic.lower().startswith(OK_LICENSES):
            continue
        if min(ii.get("width", 0), ii.get("height", 0)) < 500:
            continue
        out.append(dict(file=p["title"], url=ii.get("thumburl") or ii["url"], page=ii.get("descriptionurl"),
                        w=ii["width"], h=ii["height"], license=lic,
                        artist=_strip(m.get("Artist", {}).get("value", ""))[:80] or "unknown"))
    return out


VET = """Candidate visuals for a family-friendly YouTube Short about: {story}.
You get {n} images, numbered 0..{last} in order; their Wikimedia file names:
{names}
Judge EACH image. use=false if ANY of these:
- it is not specifically THIS story/place/person (a generic or different location, e.g. another lake, does NOT count);
- skeletons, bones, skulls, corpses, blood, wounds, weapons in use on a person, violence, gore, death scenes;
- any nudity or sexualised content (including in sculpture or painting);
- a map, diagram, chart, document/page scan, coin, stamp, book cover, modern signboard or poster;
- a collage, grid, stereo pair, before/after comparison or any multi-panel image (it must be ONE picture);
- modern people as a subject: tourists, selfies, a child or family in frame, crowds, anyone posing or walking through
  (tiny distant figures for scale are fine);
- large readable text, a watermark or logo; blurry, tiny or very dark.
score = how cinematic and scroll-stopping it is full-screen on a phone (10 = stunning).
Return JSON {{"results": [{{"i": 0, "use": bool, "score": 0-10, "what": "5 words"}}, ...one per image]}}"""


def _keywords(entry):
    ws = set(entry["key"].split("_"))
    for t in entry["wiki"]:
        ws |= set(re.findall(r"[A-Za-z]+", t))
    stop = {"temple", "lake", "fort", "the", "and", "of", "india", "group", "monuments", "national", "park", "goddess",
            "village", "story", "caves", "mahabharata", "sikhism", "hill"}
    return {w.lower() for w in ws if len(w) >= 4 and w.lower() not in stop}


BATCH = 6     # images per vision call: the free tier is ~20 requests/day/model, one call per image burned it


def images(entry, extra_queries, story_en, need=6, cache=None):
    kws = _keywords(entry)
    seen, cands = set(), []
    for q in entry["art"] + list(extra_queries or []):
        for c in commons(q):
            if c["file"] not in seen:
                seen.add(c["file"]); cands.append(c)
        if len(cands) >= 30:
            break
    junk = ("stereo", "collage", "montage", "comparison", "composite", "anaglyph", "diagram", "map of", "logo")
    cands = [c for c in cands if not any(j in c["file"].lower() for j in junk)]
    # A file whose name shares no word with the story is usually a different place ("Mystery Lake,
    # New Zealand" for Roopkund). Keep those only if too few named files exist.
    named = [c for c in cands if any(k in c["file"].lower() for k in kws)]
    cands = named + ([c for c in cands if c not in named] if len(named) < need else [])
    picked = []
    pool = []
    for c in cands[:24]:
        try:
            raw = requests.get(c["url"], headers=UA, timeout=60).content
            c["img"] = Image.open(io.BytesIO(raw)).convert("RGB")
            pool.append(c)
        except Exception:
            continue
    for i in range(0, len(pool), BATCH):
        group = pool[i:i + BATCH]
        parts = []
        for c in group:
            small = c["img"].copy(); small.thumbnail((512, 512)); b = io.BytesIO(); small.save(b, "JPEG", quality=78)
            parts.append(ai.image_part(b.getvalue()))
        try:
            v = ai.json_call(VET.format(story=story_en, n=len(group), last=len(group) - 1,
                                        names="\n".join(f"{j}: {c['file'][5:]}" for j, c in enumerate(group))),
                             models=ai.VISION_MODELS, parts=parts, temperature=0.1)
        except Exception as e:
            print("[img] vet failed", str(e)[:80]); continue
        res = {r.get("i"): r for r in v.get("results", []) if isinstance(r, dict)}
        for j, c in enumerate(group):
            r = res.get(j, {})
            print(f"[img] {r.get('use')!s:5} {r.get('score')}  {c['file'][5:60]}  ({r.get('what')})")
            if r.get("use") and (r.get("score") or 0) >= 5:
                c["score"] = r["score"]; picked.append(c)
        if len([p for p in picked if p["score"] >= 7]) >= need:
            break
    picked.sort(key=lambda c: -c["score"])
    return picked[:need]


# ── Narration ───────────────────────────────────────────────────────────────
def narrate(text, out_wav, tempo=1.08, voice="Charon", edge_voice=None):
    """Gemini TTS; when its free daily quota is spent, Microsoft edge-tts (free, no quota)."""
    src = out_wav.with_suffix(".src.wav")
    try:
        src.write_bytes(ai.tts(text, voice=voice))
    except Exception as e:
        if not edge_voice:
            raise
        print(f"[voice] Gemini TTS unavailable ({str(e)[:60]}) -> edge-tts {edge_voice}")
        mp3 = out_wav.with_suffix(".edge.mp3")
        subprocess.run([sys.executable, "-m", "edge_tts", "--voice", edge_voice, "--rate", "+4%",
                        "--text", text, "--write-media", str(mp3)], check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mp3), "-ac", "1", str(src)], check=True)
    # Trim edge silence, speed up a touch (to-the-point pacing), 48 kHz for the mix.
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-af",
                    f"silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,atempo={tempo},aresample=48000",
                    "-ac", "1", str(out_wav)], check=True)
    return duration(out_wav)


def duration(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]))


def groq_key():
    k = os.environ.get("GROQ_API_KEY")
    if k:
        return k
    p = Path(__file__).resolve().parents[2] / "quizora" / "grok_api_key.txt"
    return p.read_text().strip() if p.exists() else None


def asr(wav, lang_code):
    key = groq_key()
    if not (key and lang_code):
        return None
    mp3 = wav.with_suffix(".asr.mp3")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-b:a", "64k", str(mp3)], check=True)
    try:
        r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", headers={"Authorization": "Bearer " + key},
                          files={"file": open(mp3, "rb")}, data={"model": "whisper-large-v3", "response_format": "verbose_json",
                          "timestamp_granularities[]": "word", "language": lang_code}, timeout=180)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("[asr] failed:", str(e)[:120]); return None


def similarity(a, b):
    import difflib
    n = lambda t: re.sub(r"[\s\W_]+", "", t)
    return difflib.SequenceMatcher(None, n(a), n(b), autojunk=False).ratio()


def word_times(script_words, asr_json, total):
    """Start/end per script word. Maps each word's character position in the script onto the
    character timeline of what Whisper heard (spelling differs, the pacing does not). Falls back
    to an even character-proportional spread when there is no ASR."""
    lens = [len(w) + 1 for w in script_words]
    tot = sum(lens); cum = [sum(lens[:i]) / tot for i in range(len(lens) + 1)]
    words = (asr_json or {}).get("words") or []
    if len(words) >= 3:
        al = [max(1, len(w["word"].strip())) + 1 for w in words]
        at = sum(al); acum = [sum(al[:i]) / at for i in range(len(al) + 1)]
        pts = [(acum[i], words[i]["start"]) for i in range(len(words))] + [(1.0, words[-1]["end"])]
        def t(f):
            for (f0, t0), (f1, t1) in zip(pts, pts[1:]):
                if f <= f1:
                    return t0 + (t1 - t0) * ((f - f0) / (f1 - f0) if f1 > f0 else 0)
            return pts[-1][1]
    else:
        def t(f):
            return 0.05 + f * (total - 0.15)
    return [(t(cum[i]), t(cum[i + 1])) for i in range(len(script_words))]
