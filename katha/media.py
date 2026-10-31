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
                        artist=_strip(m.get("Artist", {}).get("value", ""))[:80] or "unknown",
                        desc=" ".join(_strip(m.get("ImageDescription", {}).get("value", "")).split())[:140]))
    return out


VET = """Candidate visuals for a family-friendly YouTube Short about: {story}.
You get {n} images, numbered 0..{last} in order; their Wikimedia file names and descriptions:
{names}
First, for EACH image, say in "where" what it really shows and where, using its file name and description
(e.g. "Soor stream near Eupen, Belgium"). Then set match=true only if that is THIS story's own place,
person, event or characters (a painting of them counts). Same-looking scenery elsewhere is match=false:
another country's river, another temple, another king, an unrelated epic scene.
Judge EACH image. use=false if ANY of these:
- match is false;
- skeletons, bones, skulls, corpses, blood, wounds, weapons in use on a person, violence, gore, death scenes;
- any nudity or sexualised content (including in sculpture or painting);
- a map, diagram, chart, document/page scan, coin, stamp, book cover, modern signboard or poster;
- a collage, grid, stereo pair, before/after comparison or any multi-panel image (it must be ONE picture);
- modern people as a subject: tourists, selfies, a child or family in frame, crowds, anyone posing or walking through
  (tiny distant figures for scale are fine);
- large readable text, a watermark or logo; blurry, tiny or very dark.
score = how cinematic and scroll-stopping it is full-screen on a phone (10 = stunning).{lines_note}
Return JSON {{"results": [{{"i": 0, "where": "what and where", "match": bool, "use": bool, "score": 0-10,
"what": "5 words"}}, ...one per image]}}"""


def _keywords(entry):
    ws = set(entry["key"].split("_"))
    for t in entry["wiki"]:
        ws |= set(re.findall(r"[A-Za-z]+", t))
    stop = {"temple", "lake", "fort", "the", "and", "of", "india", "group", "monuments", "national", "park", "goddess",
            "village", "story", "caves", "mahabharata", "sikhism", "hill"}
    return {w.lower() for w in ws if len(w) >= 4 and w.lower() not in stop}


BATCH = 6     # images per vision call: the free tier is ~20 requests/day/model, one call per image burned it


# Owner, 2026-10-31, on the first Claude Telugu long-form: "the images are from the same temple but not
# relevant to what is being spoken". images() only judged "is this the story's place?" and render showed
# them in score order, so the Lepakshi Nandi could sit under a line about the ceiling painting. With
# `lines`, the same vision call also says which narration lines each image shows (no extra calls), the
# pick keeps an image for as many lines as it can, and line_plan() tells render which image goes where.
LINES_NOTE = """
The narration, numbered line by line (it may not be in English):
{lines}
Anything a narration line mentions (a statue nearby, a painting, a hill) is part of THIS story: match=true.
For EACH image also give "lines": EVERY line whose subject you can see in it. Read each line and ask "is the
thing this line talks about in the picture?": the pillar, the ceiling or its paintings, the statue, the hill,
the doorway, the king's portrait. A ceiling photo fits a line about ceiling paintings; a photo of the temple
outside does not. Lines that only give a date, a name or a number usually fit no image. [] if none."""


# Myths, legends, saints and folk tales have no photos of their own: the Barbarika test Short showed temple
# idols for a story about a warrior's three arrows. Owner, 2026-10-31: no AI images; real paintings first.
# So these kinds search classic paintings before anything else, and the vet scores a painting of the
# characters or the scene above a modern temple photo (which still wins a line that is about the temple).
PAINT_KINDS = ("myth", "folk", "saint")
PAINT_NOTE = """
This is a myth/legend: a classic painting, miniature, mural, manuscript or relief of its characters or scenes
is the best picture there is. Score such art 2 points higher than a modern photo of a temple or idol, but keep
temple photos (use=true) for lines that talk about the temple itself."""


def _paint_queries(entry):
    # Commons search ANDs every word, so short phrases: "<name> Raja Ravi Varma" found nothing even for
    # Gajendra Moksha (10 hits for "painting", 13 for "mural"). Both the article title and the bank key, since
    # one often misses ("Baital Pachisi" has no paintings under that name). Some stories have none at all
    # (Barbarika): their temple photos stay the fallback.
    names = list(dict.fromkeys([entry["wiki"][0].split(" (")[0], entry["key"].replace("_", " ").title()]))
    return [f"{nm} {v}" for nm in names for v in ("painting", "miniature", "mural", "art")]


def images(entry, extra_queries, story_en, need=6, cache=None, lines=None):
    kws = _keywords(entry)
    seen, cands = set(), []
    # The script's own phrases name what its lines show, so they go right after the story's first search
    # instead of after every bank phrase (the 30 cap used to cut them off), and no one phrase takes it all.
    paint = entry.get("kind") in PAINT_KINDS
    qs = (_paint_queries(entry) if paint else []) + entry["art"][:1] + list(extra_queries or []) + entry["art"][1:]
    n_paint = len(_paint_queries(entry)) if paint else 0
    for qi, q in enumerate(qs):
        if qi < n_paint and len(cands) >= 20:
            continue                                 # paintings take at most 20, the story's own searches still run
        n = 0
        for c in commons(q):
            if c["file"] not in seen and n < 8:
                seen.add(c["file"]); cands.append(c); n += 1
        if len(cands) >= 36:
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
            note = LINES_NOTE.format(lines="\n".join(f"{k}: {x}" for k, x in enumerate(lines))) if lines else ""
            note += PAINT_NOTE if paint else ""
            v = ai.json_call(VET.format(story=story_en, n=len(group), last=len(group) - 1, lines_note=note,
                                        names="\n".join(f"{j}: {c['file'][5:]}" + (f" | {c['desc']}" if c.get("desc") else "")
                                                        for j, c in enumerate(group))),
                             models=ai.VISION_MODELS, parts=parts, temperature=0.1)
        except Exception as e:
            print("[img] vet failed", str(e)[:80]); continue
        res = {r.get("i"): r for r in v.get("results", []) if isinstance(r, dict)}
        for j, c in enumerate(group):
            r = res.get(j, {})
            print(f"[img] {r.get('use')!s:5} {r.get('score')}  {c['file'][5:60]}  ({r.get('where') or r.get('what')})")
            # 2026-10-26: the Surdas Short used "Soor bei Eupen" (a Belgian stream, scored 8) because
            # the vet judged mood, not subject. Now it must name the place first, and a file whose name
            # shares no word with the story needs a higher bar.
            bar = 5 if any(k in c["file"].lower() for k in kws) else 7
            if r.get("use") and r.get("match") is not False and (r.get("score") or 0) >= bar:
                c["score"] = r["score"]
                c["lines"] = sorted({int(x) for x in (r.get("lines") or []) if str(x).isdigit() and int(x) < len(lines or [])})
                c["what"] = r.get("what") or r.get("where") or ""
                c["where"] = r.get("where") or c["what"]
                picked.append(c)
        if len([p for p in picked if p["score"] >= 7]) >= need and (not lines or _coverage(picked, len(lines)) >= 0.7):
            break
    picked.sort(key=lambda c: -c["score"])
    if not lines:
        return enhance(picked[:need])
    if picked:
        _match_text(picked, lines)
    # Best image for every line that has one, then the highest scores; a few over `need` is fine when
    # each extra image is the only one that shows some line.
    out = []
    for k in range(len(lines)):
        if not any(k in c["lines"] for c in out):
            best = next((c for c in picked if k in c["lines"]), None)
            if best is not None:
                out.append(best)
    out = out[:need + 4]
    out += [c for c in picked if c not in out][:max(0, need - len(out))]
    out.sort(key=lambda c: -c["score"])
    print(f"[img] {len(out)} images cover {_coverage(out, len(lines)):.0%} of {len(lines)} lines")
    return enhance(out)


MATCH = """A narrated video shows one picture per line. Match the pictures to the lines.
LINES (numbered; they may not be in English):
{lines}
PICTURES (numbered; what each really shows):
{pics}
For EACH picture list every line whose subject is visible in it: the very object, place or scene that line talks
about (a line about a ceiling painting needs the ceiling; a temple's outside does not fit it). Lines that only
give a date, a name or a number usually fit no picture. Do not stretch.
Return JSON {{"pictures": [{{"i": 0, "lines": [1, 4]}}, ...one per picture]}}"""


def _match_text(picked, lines):
    """Second opinion on which lines each picture shows: one text-model call over the vet's own descriptions,
    added to what the vision vet said. Tested 10-31 on Lepakshi: the lite vision models skip lines at random
    (0-71% coverage over three runs of the same chapter). Never raises; on failure the vision lines stand."""
    try:
        v = ai.json_call(MATCH.format(lines="\n".join(f"{k}: {x}" for k, x in enumerate(lines)),
                                      pics="\n".join(f"{i}: {c.get('where') or c.get('what')} ({c['file'][5:80]})"
                                                      for i, c in enumerate(picked))),
                         models=ai.CHECK_MODELS, temperature=0.1)
        got = {r.get("i"): r.get("lines") or [] for r in v.get("pictures", []) if isinstance(r, dict)}
        before = _coverage(picked, len(lines))
        for i, c in enumerate(picked):
            c["lines"] = sorted(set(c.get("lines", [])) |
                                {int(x) for x in got.get(i, []) if str(x).isdigit() and int(x) < len(lines)})
        print(f"[img] text match: {before:.0%} -> {_coverage(picked, len(lines)):.0%} of lines")
    except Exception as e:
        print("[img] text match failed", str(e)[:80])


def _coverage(shots, n):
    return len({k for c in shots for k in c.get("lines", [])}) / max(n, 1)


def line_plan(shots, n):
    """For each of n lines, the shot indices to show, best first.

    An image that fits only this line beats one that fits several (the Lepakshi Nandi line took a corridor shot
    the vet had loosely tagged for three lines over the Nandi photo itself); the score breaks ties.
    A line no image shows stays on the subject of the line before it (it usually goes on about the same thing:
    "So is the pillar hanging in the air?") but steps to that subject's next picture; opening lines before any
    match cycle through the best images, as before 10-31. The first version held ONE picture for every
    unmatched line: the Barbarika test Short sat on a single idol photo for 27 of its 37 s."""
    plan = [sorted((i for i, c in enumerate(shots) if k in c.get("lines", [])),
                   key=lambda i: (len(shots[i].get("lines", [])), -shots[i]["score"])) for k in range(n)]
    by_score = sorted(range(len(shots)), key=lambda i: -shots[i]["score"]) or [0]
    general = [i for i in by_score if not shots[i].get("lines")] or by_score
    g = 0
    for k in range(n):
        prev = plan[k - 1][0] if k else None
        if plan[k]:
            if plan[k][0] == prev and len(plan[k]) > 1:          # same subject as the line before: next picture
                plan[k] = plan[k][1:] + plan[k][:1]
            continue
        src = plan[k - 1] if k else []
        if len(src) > 1:
            plan[k] = src[1:] + src[:1]
        else:
            pick = general[g % len(general)]; g += 1
            if pick == prev and len(general) > 1:
                pick = general[g % len(general)]; g += 1
            plan[k] = [pick]
    return plan


# PhotoCraft (github.com/storytold/photocraft) headless clean-up before render's own grade():
# Auto Tone, a gentle shadow lift and Smart Sharpen. Tested 2026-10-23 on 18 story images: dark
# cave/temple shots got their carvings back and hazy mountains their depth; already-harsh shots
# barely change. Optional: no CLI on PATH, or any failure, keeps the originals.
PC_ACTIONS = [["image.autoTone", {}],
              ["image.adjustments.shadowsHighlights", {"shadowAmount": 20, "highlightAmount": 10}],
              ["filter.sharpen.smartSharpen", {"amount": 60, "radius": 1.0, "reduceNoise": 15}]]


def enhance(shots):
    import shutil, tempfile
    cli = os.environ.get("PHOTOCRAFT_CLI") or shutil.which("photocraft-cli")
    if not (cli and shots):
        return shots
    try:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); (d / "in").mkdir(); (d / "out").mkdir()
            (d / "a.json").write_text(json.dumps(PC_ACTIONS))
            for i, c in enumerate(shots):
                c["img"].save(d / "in" / f"{i:02d}.png")
            subprocess.run([cli, "batch", "--actions", str(d / "a.json"), "--in", str(d / "in"), "--out", str(d / "out"),
                            "--format", "png"], check=True, capture_output=True, timeout=240)
            out = [Image.open(d / "out" / f"{i:02d}.png").convert("RGB") for i in range(len(shots))]
        for c, im in zip(shots, out):
            c["img"] = im
        print(f"[img] PhotoCraft enhanced {len(out)} images")
    except Exception as e:
        print("[img] PhotoCraft skipped:", str(e)[:120])
    return shots


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
        # The Multilingual voices (newer generation, 2026-10-27) read ~8% slower than the old ones at
        # the same rate, so they get +12% to keep the +4% pacing.
        rate = "+12%" if "Multilingual" in edge_voice else "+4%"
        subprocess.run([sys.executable, "-m", "edge_tts", "--voice", edge_voice, "--rate", rate,
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


def pauses(wav, db=-38, min_d=0.12):
    """(start, end) of every silence in the clean narration track (before music is mixed in)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af", f"silencedetect=n={db}dB:d={min_d}",
                        "-f", "null", "-"], capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    out = []
    for a, b in zip(st, en):                      # a breath blip splits one pause in two; rejoin
        if out and a - out[-1][1] < 0.2:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def sentence_word_times(sentences, wav, total):
    """Start/end per script word, anchored on the narrator's pauses between sentences.

    Whisper's word timestamps on long Hindi/Telugu narration sometimes skip or squash a whole
    stretch (Surdas hi and Krishnadevaraya te, 2026-10-22: captions ran ~15 s ahead of the voice,
    then froze on one line for 16 s). Pauses in the clean TTS track don't drift: each sentence
    boundary snaps to the strongest pause near where its character share says it should fall,
    and words are spread by characters inside the sentence, so any error stays within one
    sentence. Returns None when there aren't enough pauses to anchor on."""
    n = len(sentences)
    if n < 2:
        return None
    ps = [(a, b) for a, b in pauses(wav) if 0.3 < a and b < total - 0.3]
    if len(ps) < n - 1:
        return None
    w = [len(s) + 1 for s in sentences]
    exp = [sum(w[:i + 1]) / sum(w) * total for i in range(n - 1)]
    # Pick n-1 pauses in order (DP): close to the expected boundary, longer pauses preferred.
    cost = lambda i, j: abs((ps[j][0] + ps[j][1]) / 2 - exp[i]) - 2.5 * min(ps[j][1] - ps[j][0], 0.8)
    INF = float("inf"); m = len(ps)
    best = [[INF] * m for _ in range(n - 1)]; back = [[-1] * m for _ in range(n - 1)]
    for j in range(m):
        best[0][j] = cost(0, j)
    for i in range(1, n - 1):
        run, arg = INF, -1
        for j in range(m):
            if j > 0 and best[i - 1][j - 1] < run:
                run, arg = best[i - 1][j - 1], j - 1
            if arg >= 0:
                best[i][j] = run + cost(i, j); back[i][j] = arg
    j = min(range(m), key=lambda k: best[n - 2][k])
    if best[n - 2][j] == INF:
        return None
    pick = []
    for i in range(n - 2, -1, -1):
        pick.append(ps[j]); j = back[i][j]
    pick.reverse()
    spans = [(0.05 if i == 0 else pick[i - 1][1], pick[i][0] if i < n - 1 else total - 0.1) for i in range(n)]
    out = []
    for s, (a, b) in zip(sentences, spans):
        ws = s.split(); lens = [len(x) + 1 for x in ws]; tot = sum(lens); c = 0
        for L in lens:
            out.append((a + (b - a) * c / tot, a + (b - a) * (c + L) / tot)); c += L
    return out
