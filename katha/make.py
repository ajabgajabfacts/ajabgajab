"""Ajab Gajab story Shorts: pick -> write -> fact-check -> images -> voice -> render -> upload.

    python katha/make.py --lang hi                  # next story, render + upload
    python katha/make.py --lang ta --key kannagi --no-upload   # local test render
    python katha/make.py --lang hi --dry            # script only, print it

Env (CI): GEMINI_API_KEY, GROQ_API_KEY, CHANNEL_CONFIG. Locally the key files are used.
"""
import argparse, datetime as dt, json, os, random, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bank, media, render, write
from langs import LANGS

LEDGER = HERE / "ledger.json"
MUSIC = HERE.parent / "music"
# Calm/cinematic beds only; the upbeat tracks fight a story voice.
MUSIC_OK = ["Dream Escape - The Tides.mp3", "Horizons - Alex Jones _ Xander Jones.mp3",
            "The Light - Alex Jones _ Xander Jones.mp3", "Rain Over Kyoto Station - The Mini Vandals.mp3"]


def ledger():
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []


def pick(lang, force_key=None):
    if force_key:
        return next(s for s in bank.S if s["key"] == force_key)
    done = {(r["key"], r["lang"]) for r in ledger() if r.get("status") in ("posted", "failed_check")}
    regional = [s for s in bank.S if s["lang"] == lang and (s["key"], lang) not in done]
    common = [s for s in bank.S if s["lang"] == "all" and (s["key"], lang) not in done]
    n = len([r for r in ledger() if r["lang"] == lang])
    # Regional first 2 of every 3 slots: their own place/saint/king is what this audience relates to.
    pool = regional if (regional and (n % 3 != 2 or not common)) else (common or regional)
    if not pool:
        raise SystemExit(f"bank exhausted for {lang}")
    return random.Random(f"{lang}{n}").choice(pool)


def credits(sources, shots):
    lines = ["Source: " + ", ".join(f"Wikipedia - {s['title']} (CC BY-SA 4.0)" for s in sources)]
    lines.append("Images (Wikimedia Commons):")
    for c in shots:
        lines.append(f"- {c['file'][5:]} - {c['artist']} - {c['license']}")
    return "\n".join(lines)


PLAYLISTS = HERE / "playlists.json"


def add_to_playlist(yt, vid, lang):
    """One playlist per language, so a viewer who likes one Tamil story can binge the rest.
    IDs are cached in playlists.json (tracked) so CI never mints duplicates."""
    from langs import LANGS
    cache = json.loads(PLAYLISTS.read_text(encoding="utf-8")) if PLAYLISTS.exists() else {}
    L = LANGS[lang]
    pid = cache.get(lang)
    try:
        if not pid:
            title = f"{L['name']} Stories | {L['brand']}"
            pl = yt.playlists().insert(part="snippet,status", body={
                "snippet": {"title": title, "description": f"Ajab Gajab stories in {L['name']}: myths, legends, "
                            "real places, science and more. Fact-checked against Wikipedia.",
                            "defaultLanguage": lang},
                "status": {"privacyStatus": "public"}}).execute()
            pid = cache[lang] = pl["id"]
            PLAYLISTS.write_text(json.dumps(cache, indent=1), encoding="utf-8")
            print(f"[playlist] created {title} ({pid})")
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
    except Exception as e:
        print("[playlist] failed:", str(e)[:150])


def upload(mp4, meta, cfg_json, thumb=None):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    c = json.loads(cfg_json)["credentials"]
    creds = Credentials.from_authorized_user_info(c)
    if not creds.valid:
        creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {"snippet": {"title": meta["title"][:100], "description": meta["description"][:4900],
                        "tags": meta["tags"][:15], "categoryId": "24",
                        "defaultLanguage": meta["lang"], "defaultAudioLanguage": meta["lang"]},
            "status": {"privacyStatus": meta.get("privacy", "public"), "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": False}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(mp4), chunksize=-1, resumable=True, mimetype="video/mp4"))
    resp = None
    for attempt in range(5):
        try:
            while resp is None:
                _, resp = req.next_chunk()
            break
        except Exception as e:
            if attempt == 4:
                raise
            print("[upload] retry", str(e)[:100]); time.sleep(10 * (attempt + 1))
    vid = resp["id"]
    if thumb:
        try:                                     # custom thumbnails need a phone-verified channel
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")).execute()
        except Exception as e:
            print("[upload] thumbnail failed:", str(e)[:150])
    add_to_playlist(yt, vid, meta["lang"])
    if meta.get("comment"):
        try:
            yt.commentThreads().insert(part="snippet", body={"snippet": {"videoId": vid, "topLevelComment": {
                "snippet": {"textOriginal": meta["comment"]}}}}).execute()
        except Exception as e:
            print("[upload] comment failed:", str(e)[:120])
    return vid


# 4 slots a day on one channel. From 2026-10-20 (slot 3 onward): Telugu every evening (slot 3, 20:35 IST), Hindi once
# (slot 2), and the other eight languages rotating through slots 0 and 1, each every 4 days.
# Why: first two days, Hindi 3 posts all under 40 views; Kannappa in Telugu 1,370 in 18 h, Tamil 326.
# Before 10-20 it was Hindi on 0 and 2 with nine regional languages on 1 and 3 (kept for old dates).
REGIONAL = ["ta", "te", "bn", "mr", "kn", "ml", "gu", "or", "pa"]
EPOCH = dt.date(2026, 10, 19)
ROTATING = ["ta", "bn", "mr", "kn", "ml", "gu", "or", "pa"]
EPOCH2 = dt.date(2026, 10, 20)


def slot_lang(slot, day=None):
    day = day or dt.date.today()
    if day < EPOCH2:
        d = (day - EPOCH).days
        return "hi" if slot in (0, 2) else REGIONAL[(2 * d + (slot == 3)) % len(REGIONAL)]
    if slot == 3:
        return "te"
    if slot == 2:
        return "hi"
    return ROTATING[(2 * (day - EPOCH2).days + slot) % len(ROTATING)]


class StoryFailed(Exception):
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="hi", help="language code, or 'auto' to use --slot's rotation")
    ap.add_argument("--slot", type=int, default=int(os.environ.get("KATHA_SLOT", "-1")))
    ap.add_argument("--key")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--reuse", action="store_true", help="reuse script/images/voice already in the work dir")
    ap.add_argument("--out", default=str(HERE / "out"))
    a = ap.parse_args()
    if a.lang == "auto":
        if a.slot < 0:
            raise SystemExit("--lang auto needs --slot 0-3 (or KATHA_SLOT)")
        a.lang = slot_lang(a.slot)
    today = str(dt.date.today())
    if a.slot >= 0 and not a.no_upload and not os.environ.get("FORCE_POST") and any(
            r.get("date") == today and r.get("slot") == a.slot and r.get("status") == "posted" for r in ledger()):
        print(f"[katha] slot {a.slot} already posted today - nothing to do"); return
    L = LANGS[a.lang]
    for attempt in range(3):                     # a story that fails its checks is retired; try the next one
        e = pick(a.lang, a.key)
        try:
            return produce(a, L, e)
        except StoryFailed as err:
            print(f"[katha] {e['key']}/{a.lang} FAILED: {err}")
            if a.key or a.no_upload:
                raise SystemExit(1)
            led = ledger(); led.append(dict(key=e["key"], lang=a.lang, date=today, status="failed_check", why=str(err)[:200]))
            LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    raise SystemExit("three stories in a row failed - see log")


def produce(a, L, e):
    print(f"[katha] {a.lang} / {e['key']} ({e['kind']})")
    work = Path(a.out) / f"{dt.date.today()}_{a.lang}_{e['key']}"; work.mkdir(parents=True, exist_ok=True)

    sources = media.wiki(e["wiki"])
    if not sources:
        raise StoryFailed("no source text")
    src = "\n\n".join(f"### {s['title']}\n{s['text']}" for s in sources)
    sj = work / "script.json"
    try:
        if a.reuse and sj.exists():
            d = json.loads(sj.read_text(encoding="utf-8")); s, chk = d["script"], d["check"]
        else:
            s, chk = write.write(e, a.lang, L, src)
    except RuntimeError as err:
        raise StoryFailed(err)
    (work / "script.json").write_text(json.dumps(dict(script=s, check=chk), ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(s["sentences"]))
    if a.dry:
        return

    story_en = f"{e['key'].replace('_', ' ')} - " + "; ".join(s.get("claims_en", [])[:4])
    from PIL import Image
    sh = work / "shots.json"
    if a.reuse and sh.exists():
        shots = json.loads(sh.read_text(encoding="utf-8"))
        for i, c in enumerate(shots):
            c["img"] = Image.open(work / f"img_{i}.jpg")
    else:
        shots = media.images(e, s.get("visuals"), story_en, need=6)
        for i, c in enumerate(shots):
            c["img"].save(work / f"img_{i}.jpg", quality=92)
        sh.write_text(json.dumps([{k: v for k, v in c.items() if k != "img"} for c in shots], ensure_ascii=False, indent=1), encoding="utf-8")
    if len(shots) < 3:
        raise StoryFailed(f"only {len(shots)} usable images")

    text = " ".join(s["sentences"])
    voice = work / "voice.wav"
    for attempt in range(2):
        if a.reuse and voice.exists() and (work / "asr.json").exists():
            D = media.duration(voice); asr = json.loads((work / "asr.json").read_text(encoding="utf-8")); break
        D = media.narrate(text, voice, edge_voice=L.get("edge"))
        asr = media.asr(voice, L["whisper"])
        if asr:
            (work / "asr.json").write_text(json.dumps(asr, ensure_ascii=False), encoding="utf-8")
        sim = media.similarity(text, asr["text"]) if asr else None
        print(f"[voice] {D:.1f}s  asr-match={sim}")
        if sim is None or sim >= 0.55:
            break
    words = text.split()
    wt = media.word_times(words, asr, D)
    total = D + 0.8
    music = MUSIC / random.Random(e["key"]).choice(MUSIC_OK)
    job = dict(L=L, sentences=s["sentences"], word_times=wt, hook_text=s["hook_text"], kicker=s["kicker"],
               cta=s.get("cta"), shots=[c["img"] for c in shots], voice=voice,
               music=music if music.exists() else None, duration=total)
    t0 = time.time()
    mp4 = render.render(job, work / "short.mp4", work)
    print(f"[render] {mp4} in {time.time() - t0:.0f}s")

    tags = [h.lstrip("#").strip() for h in s.get("hashtags", [])]
    desc = s["description"] + "\n\n" + " ".join("#" + t.replace(" ", "") for t in tags[:5]) + "\n\n" + credits(sources, shots)
    meta = dict(title=s["title"], description=desc, tags=tags + ["shorts", "ajab gajab", L["name"]], lang=a.lang,
                comment=s["sentences"][-1])
    (work / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.no_upload:
        return
    cfg = os.environ.get("CHANNEL_CONFIG") or (HERE.parent / "CHANNEL_Ajab_Gajab_Facts_CONFIG.json").read_text()
    vid = upload(mp4, meta, cfg)
    print(f"[upload] https://youtube.com/shorts/{vid}")
    led = ledger()
    led.append(dict(key=e["key"], lang=a.lang, date=str(dt.date.today()), utc=dt.datetime.now(dt.timezone.utc).strftime("%H:%M"),
                    status="posted", video_id=vid, title=s["title"], seconds=round(total, 1),
                    slot=a.slot if a.slot >= 0 else None))
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
