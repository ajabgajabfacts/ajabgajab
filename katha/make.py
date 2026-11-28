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
import bank, festivals, insights, media, render, trends, write
from langs import LANGS

LEDGER = HERE / "ledger.json"
PREWRITTEN = HERE / "prewritten"         # scripts written ahead with spare quota (prewrite.py)
BACKUP = HERE / "backup"                 # emergency scripts from the weekly Claude routine (backup.py)
MUSIC = HERE.parent / "music"
# Calm/cinematic beds only; the upbeat tracks fight a story voice.
MUSIC_OK = ["Dream Escape - The Tides.mp3", "Horizons - Alex Jones _ Xander Jones.mp3",
            "The Light - Alex Jones _ Xander Jones.mp3", "Rain Over Kyoto Station - The Mini Vandals.mp3"]


# Story Shorts use our own synthesised music (genmusic.py, copied from quizora/), the mood picked
# from the story's kind; the library tracks above are only the fallback. Owner approved the
# mystery / epic / devotional / wonder samples 2026-10-23.
MOOD_BY_KIND = {"myth": "devotional", "saint": "devotional", "history": "epic", "people": "epic", "sport": "epic",
                "folk": "mystery"}          # everything else (wonder, engineering, nature, food, space...) -> "wonder"


def story_music(e, seconds, work):
    try:
        import genmusic, zlib
        mood = MOOD_BY_KIND.get(e.get("kind"), "wonder")
        p = genmusic.generate(Path(work) / "music.wav", seconds + 1, seed=zlib.crc32(e["key"].encode()), mood=mood)
        print(f"[music] genmusic {mood}")
        return p
    except Exception as ex:
        print(f"[music] genmusic failed ({ex}); library track")
        m = MUSIC / random.Random(e["key"]).choice(MUSIC_OK)
        return m if m.exists() else None


def ledger():
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []


def redos(day=None):
    """(key, lang) of deleted Shorts to post again, oldest first, until the repost is in the ledger.
    A repost made today still counts, so a slot's language stays the same on a same-day retry.
    (2026-10-23: five 60-86 s Shorts whose captions drifted off the voice were deleted for reposting.)"""
    day = str(day or dt.date.today()); led = ledger()
    done = {(r["key"], r["lang"]) for r in led if r.get("status") == "posted" and r.get("date", "") < day}
    out = []
    for r in led:
        k = (r["key"], r["lang"])
        if r.get("status") == "redo" and k not in done and k not in out:
            out.append(k)
    return out


# Festival stories post only in the evening slots (2 = 18:05 IST, 3 = 20:35 IST): the Rajyotsava Short went up
# by hand at 15:29 IST and got 6 views in a day. A run with no slot (-1, manual) may still use them.
EVENING = (2, 3, -1, 6)   # 6 = festivals.EXTRA_SLOT, 19:05 IST on festival days
FEST_MIN_IMAGES = 6     # Rajyotsava had 4 usable images (25% of lines); the Mysore hits had plenty


def pick(lang, force_key=None, exclude=(), day=None, slot=-1):
    if force_key:
        return next(s for s in bank.S if s["key"] == force_key)
    done = {(r["key"], r["lang"]) for r in ledger() if r.get("status") in ("posted", "failed_check")}
    done |= {(k, lang) for k in exclude}
    # What the audience is talking about today goes first (trends.py, 2026-11-14: the daily Claude trend scout).
    # A script the scout wrote must pass Gemini's check before it posts; with no script, Gemini writes one now.
    for k in trends.keys_for(lang, day or dt.date.today()):
        pre = PREWRITTEN / f"{lang}_{k}.json"
        s = next((s for s in bank.S if s["key"] == k), None)
        if s and (k, lang) not in done and (not pre.exists() or ALLOW_UNVERIFIED or _verified(pre)):
            print(f"[trend] {lang}: {k}")
            return s
    # A festival happening now goes first (festivals.py, 2026-11-01): the only breakouts we ever had were
    # festival-day stories (Mysore Palace 89k, Dasara elephant 28k on Jamboo Savari day).
    for k in (festivals.keys_for(lang, day or dt.date.today()) if slot in EVENING else []):
        if (k, lang) not in done:
            s = next((s for s in bank.S if s["key"] == k), None)
            if s:
                print(f"[festival] {lang}: {k}")
                return s
    # Backup stories are held for a day Gemini can't write; main() moves one into PREWRITTEN then.
    done |= {(p.stem[len(lang) + 1:], lang) for p in BACKUP.glob(f"{lang}_*.json")}
    for k, l in redos():
        if l == lang and (k, l) not in done:
            return next(s for s in bank.S if s["key"] == k)
    # A script written ahead (prewrite.py) goes next: it costs this run no text quota. One the Claude
    # routine wrote waits for Gemini's double-check ("verified"), unless Gemini is down (main()).
    for p in sorted(PREWRITTEN.glob(f"{lang}_*.json")):
        k = p.stem[len(lang) + 1:]
        s = next((s for s in bank.S if s["key"] == k), None)
        if s and (k, lang) not in done and (ALLOW_UNVERIFIED or _verified(p)):
            return s
    held = festivals.reserved(day or dt.date.today())        # saved for their festival's days
    done |= {(k, lang) for k in held}
    regional = [s for s in bank.S if s["lang"] == lang and (s["key"], lang) not in done]
    # "all" means pan-Indian; English is a different channel with its own world stories.
    common = [s for s in bank.S if s["lang"] == "all" and (s["key"], lang) not in done] if lang != "en" else []
    if hi_devotional(lang, slot, day):            # Hindi devotional week: myths and saints only (see HI_DEV)
        regional = [s for s in regional if s["kind"] in DEVOTIONAL_KINDS]
        common = [s for s in common if s["kind"] in DEVOTIONAL_KINDS]
    n = len([r for r in ledger() if r["lang"] == lang])
    # Regional first 2 of every 3 slots: their own place/saint/king is what this audience relates to.
    pool = regional if (regional and (n % 3 != 2 or not common)) else (common or regional)
    if not pool:
        raise SystemExit(f"bank exhausted for {lang}")
    # Story types that did well on our channel get picked more often (katha/insights.py); a kind
    # with no data yet stays at 1.0. English is its own channel, so it reads its own weights.
    kw = (insights.load().get("channels", {}).get("en" if lang == "en" else "ajab", {}) or {}).get("kind_weights") or {}
    return random.Random(f"{lang}{n}").choices(pool, [kw.get(s["kind"], {}).get("w", 1.0) for s in pool])[0]


def credits(sources, shots):
    lines = ["Source: " + ", ".join(f"Wikipedia - {s['title']} (CC BY-SA 4.0)" for s in sources)]
    commons = [c for c in shots if not c.get("ai")]
    if commons:
        lines.append("Images (Wikimedia Commons):")
        for c in commons:
            lines.append(f"- {c['file'][5:]} - {c['artist']} - {c['license']}")
    if any(c.get("ai") for c in shots):
        lines.append("Illustrations: AI-generated for this story (aiart.py).")
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
                "snippet": {"title": title, "description": f"{L.get('channel', ('Ajab Gajab',))[0]} stories in {L['name']}: myths, legends, "
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


def upscale_4k(src):
    """2x lanczos upscale for the YouTube upload only (owner, 2026-10-23: Shorts in 4K too).

    YouTube serves 4K uploads with VP9/AV1 at a higher bitrate, so even 1080p viewers get a cleaner stream.
    Facebook keeps the 1080p file: Reels cap at 1080x1920. Anything already above 1080p, or any ffmpeg
    failure, returns the original path, so an upload is never lost to this step.
    """
    import subprocess
    from pathlib import Path
    src = Path(src)
    try:
        w, h = map(int, subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", str(src)], text=True).strip().split("x"))
        secs = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                              "-of", "csv=p=0", str(src)], text=True))
        # Shorts encode at medium in a few minutes on a 2-core runner; a 10-minute long-form at medium could
        # take most of the job, so long videos use veryfast at a lower CRF. Shorts get at most 10 minutes.
        # 2026-11-14: Shorts went medium -> veryfast. The 4K copy is identical to the eye (SSIM 0.999 vs medium)
        # and ~40% faster, and this repo is on pace for ~4,200 Actions minutes in November against 2,000 free.
        preset, crf, limit = ("veryfast", "16", 600) if secs <= 120 else ("veryfast", "15", 5400)
        if max(w, h) > 1920:
            return src
        dst = src.with_name(src.stem + "_4k.mp4")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf", f"scale={w * 2}:{h * 2}:flags=lanczos",
                        "-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p",
                        "-c:a", "copy", "-movflags", "+faststart", str(dst)], check=True, timeout=limit)
        print(f"[4K] {w}x{h} -> {w * 2}x{h * 2}: {dst.name}")
        return dst
    except Exception as e:
        print(f"[4K] skipped ({e}); uploading the original")
        return src


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
                       "containsSyntheticMedia": bool(meta.get("synthetic"))}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(upscale_4k(mp4)), chunksize=-1, resumable=True, mimetype="video/mp4"))
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
    if meta.get("captions") and captions_fit(meta):
        import ytcaptions
        ytcaptions.upload(yt, vid, meta["captions"], meta["lang"])
    return vid


def captions_fit(meta):
    """Exact-script caption track (ytcaptions.py, 2026-11-01): 400 quota units on top of a 1600 upload.
    WTR (en) has its own Cloud project with room to spare. Ajab's project carries 4 Shorts a day, and on
    long-form days (longplan: Sunday hi, Wednesday te, plus EXTRA dates) the long-form too: 4 x 2,100 for
    captioned Shorts + 2,150 for the long-form would cross the 10,000 daily quota, and an over-quota caption
    call could make that day's LAST upload fail. So on those days only the long-form gets captions. The
    quota day is Pacific time."""
    if meta["lang"] == "en" or meta.get("long"):
        return True
    if festivals.extra_slot_on(dt.date.today(), _done_before(dt.date.today())):
        print("[captions] skipped: extra festival Short today on the Ajab quota")
        return False
    from zoneinfo import ZoneInfo
    import longplan
    day = dt.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    if longplan.LONG_DAYS.get(day.weekday()) or str(day) in dict(longplan.EXTRA):
        print("[captions] skipped: long-form day on the Ajab quota")
        return False
    return True


# 4 slots a day on one channel. From 2026-10-20 (slot 3 onward): Telugu every evening (slot 3, 20:35 IST), Hindi once
# (slot 2), and the other eight languages rotating through slots 0 and 1, each every 4 days.
# Why: first two days, Hindi 3 posts all under 40 views; Kannappa in Telugu 1,370 in 18 h, Tamil 326.
# Before 10-20 it was Hindi on 0 and 2 with nine regional languages on 1 and 3 (kept for old dates).
REGIONAL = ["ta", "te", "bn", "mr", "kn", "ml", "gu", "or", "pa"]
EPOCH = dt.date(2026, 10, 19)
# kn twice: Mysore Palace (14.3k, 2026-10-21) is the channel record; ta and bn were next best of the rotation.
ROTATING = ["ta", "kn", "bn", "mr", "kn", "ml", "gu", "or", "pa"]
EPOCH2 = dt.date(2026, 10, 20)
KN_DAILY = dt.date(2026, 10, 26)
# Kannada-every-day ENDED 2026-11-28: 28 kn Shorts since the slot began, median 10 views (ta 398, gu 122, te ~250).
# The Mysore records were Dasara-day event spikes; the feed does not seed our everyday kn Shorts. Slot 0 now draws
# from the insights weights like slot 1, where kn keeps its (lowest) weight so it is still tested.
KN_OFF = dt.date(2026, 11, 28)
# From 2026-11-01 slot 2 is no longer Hindi every day (owner approved the content strategy 10-31): Hindi Shorts
# had the channel's lowest median (44 views, slot 2, 10-19..10-29) while the rotating regional languages ran
# ~100-580. Slot 2 now draws from the same weights as slot 1, with Hindi kept in at the lowest weight so it is
# still tested. Hindi long-form (katha_long.yml) is unchanged.
HI_OFF = dt.date(2026, 11, 1)
# Hindi devotional week (owner 2026-11-23: "yes go for hindi too"). The Hindi myth channels lead the whole niche
# (Dev Kathan Shorts: median ~600k views, Hindu IQ ~500k), and our Hindi was judged on the old look (temple photos,
# place mysteries). With AI character art, character-first stories and big captions, slot 2 is Hindi and devotional
# (myth/saint stories) every day of this window. A festival language still takes the evening slot on its day.
# Judge ~12-01: Hindi slot-2 views vs its old median (44) and vs the other slots in the same week.
HI_DEV = (dt.date(2026, 11, 23), dt.date(2026, 11, 30))
DEVOTIONAL_KINDS = ("myth", "saint")


def hi_devotional(lang, slot, day=None):
    day = day or dt.date.today()
    return lang == "hi" and slot == 2 and HI_DEV[0] <= day <= HI_DEV[1]


def _done_before(day):
    return {(r["key"], r["lang"]) for r in ledger()
            if r.get("status") in ("posted", "failed_check") and r.get("date", "") < str(day)}


def _focus_lang(slot, day):
    """Telugu + Tamil channel (festivals.FOCUS, owner 2026-11-28): 08:05 IST Tamil, 12:05 Telugu, 18:05 Tamil,
    20:35 Telugu (slot 3, above). The 18:05 evening slot goes to a Tamil or Kannada event or trend story when one
    is waiting, which is the only way Kannada still posts. Telugu events need no routing: pick() serves a
    language's trend stories first in any slot, and festival stories in its evening slot 3."""
    done = _done_before(day)                      # start-of-day view: every slot that day sees the same list
    want = [l for l in dict.fromkeys(festivals.evening_langs(day, done) + trends.langs_for(day, done))
            if l in ("ta", "kn")]
    if slot == 2 and want:
        return want[0]
    if slot == festivals.EXTRA_SLOT and len(want) > 1:
        return want[1]
    return {0: "ta", 1: "te", 2: "ta"}.get(slot, "ta")


def slot_lang(slot, day=None):
    day = day or dt.date.today()
    if day < EPOCH2:
        d = (day - EPOCH).days
        return "hi" if slot in (0, 2) else REGIONAL[(2 * d + (slot == 3)) % len(REGIONAL)]
    if slot == 3:
        return "te"
    if day >= festivals.FOCUS:
        return _focus_lang(slot, day)
    if slot == 2 and day < HI_OFF:
        return "hi"
    if slot == 2 and HI_DEV[0] <= day <= HI_DEV[1] and not festivals.evening_langs(day, _done_before(day)):
        return "hi"
    # From 2026-10-26 slot 0 is Kannada every day (owner): kn is the channel's record language
    # (Mysore Palace 70k, elephant 22k) but the weighted draw left it out 10-23..10-25.
    if slot == 0 and KN_DAILY <= day < KN_OFF:
        return "kn"
    # Trend languages (trends.py, 2026-11-14) without a fixed slot of their own take rotating slot 1, and slot 2
    # when no festival wants it. Start-of-day view, so every slot that day sees the same list.
    if slot in (1, 2) and day >= trends.FROM:
        own = ("kn", "te", "en") if day < KN_OFF else ("te", "en")   # languages with a fixed slot of their own
        tl = [l for l in trends.langs_for(day, _done_before(day)) if l not in own]
        if slot == 1 and tl:
            return tl[0]
        if slot == 2 and len(tl) > 1 and not (day >= HI_OFF and festivals.evening_langs(day, _done_before(day))):
            return tl[1]
    # Festival languages take the evening rotating slot (festivals.py): slot 2 gets the first language an
    # active event still has an untold story for, Kannada included (slot 0 is a morning slot). Telugu's
    # evening slot 3 picks its own events.
    if slot in (2, festivals.EXTRA_SLOT) and day >= HI_OFF:
        want = festivals.evening_langs(day, _done_before(day))   # start-of-day view: same list for every slot
        i = 0 if slot == 2 else 1
        if len(want) > i:
            return want[i]
    # Reposts of deleted Shorts in the rotating languages go first: slot 0 the oldest, slot 1 the next.
    rot = [l for k, l in redos(day) if l not in ("te", "hi", "en")]
    rot = list(dict.fromkeys(rot))
    if KN_DAILY <= day < KN_OFF:
        rot = [l for l in rot if l != "kn"]
        if len(rot) > slot - 1:
            return rot[slot - 1]                     # slot 1 the oldest repost, slot 2 the next
    elif len(rot) > slot:
        return rot[slot]
    # From 2026-10-23 the rotating slots follow katha/insights.py's language weights (our own
    # views, shrunk and clamped so every language keeps being tested). Seeded by the date, so a
    # retry the same day gets the same language; slot 1 never repeats slot 0's language.
    lw = (insights.load().get("channels", {}).get("ajab", {}) or {}).get("lang_weights") or {}
    if lw:
        w = {l: lw[l]["w"] for l in lw}
        if slot == 2:
            w.setdefault("hi", min(w.values()))
        for earlier in range(slot):                  # never repeat a language already posted earlier today
            w.pop(slot_lang(earlier, day), None)
        for l in festivals.evening_langs(day, _done_before(day))[:2]:   # ...or a festival posts this evening
            w.pop(l, None)
        if slot == 0 and day >= KN_OFF and day >= trends.FROM:      # ...or a trend story takes slot 1/2 later today
            for l in trends.langs_for(day, _done_before(day))[:2]:
                w.pop(l, None)
        for r in ledger():                           # ...including what actually posted (a festival may have
            if r.get("date") == str(day) and r.get("status") == "posted":   # taken that slot's language)
                w.pop(r.get("lang"), None)
        langs = sorted(w)
        return random.Random(f"{day}/{slot}").choices(langs, [w[l] for l in langs])[0]
    # No weights (insights.json stale, e.g. after the 11-15..11-23 Actions outage): fixed rotation, but never a
    # language an earlier slot already has today (12-01 drew kn for slots 0 and 1 on a stale file).
    taken = {slot_lang(earlier, day) for earlier in range(slot)}
    k = 2 * (day - EPOCH2).days + slot
    for i in range(len(ROTATING)):
        if ROTATING[(k + i) % len(ROTATING)] not in taken:
            return ROTATING[(k + i) % len(ROTATING)]
    return ROTATING[k % len(ROTATING)]


class StoryFailed(Exception):
    pass


ALLOW_UNVERIFIED = False


def _verified(p):
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("verified", True)
    except Exception:
        return False


class GeminiDown(Exception):
    """The writer could not reach a model (quota, outage) - not the story's fault, so never retire it."""


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
        e = pick(a.lang, a.key, slot=a.slot)
        try:
            return produce(a, L, e)
        except GeminiDown as err:
            if a.key:
                raise
            global ALLOW_UNVERIFIED
            unverified = [p for p in PREWRITTEN.glob(f"{a.lang}_*.json") if not _verified(p)]
            spare = sorted(BACKUP.glob(f"{a.lang}_*.json"))
            if unverified and not ALLOW_UNVERIFIED:
                ALLOW_UNVERIFIED = True              # Claude's self-checked script beats no post
                print(f"[katha] Gemini can't write ({str(err)[:80]}) -> unverified Claude script")
            elif spare:
                ALLOW_UNVERIFIED = True              # a backup may not have had Gemini's check yet
                PREWRITTEN.mkdir(exist_ok=True)
                spare[0].rename(PREWRITTEN / spare[0].name)
                print(f"[katha] Gemini can't write ({str(err)[:80]}) -> backup script {spare[0].name}")
            else:
                raise
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
    # Our best titles in this language so far, as style examples for the writer (katha/insights.py).
    ch = insights.load().get("channels", {}).get("en" if a.lang == "en" else "ajab", {}) or {}
    e = dict(e, proven=(ch.get("proven_titles") or {}).get(a.lang, []))

    sources = media.wiki(e["wiki"])
    if not sources:
        raise StoryFailed("no source text")
    src = "\n\n".join(f"### {s['title']}\n{s['text']}" for s in sources)
    sj = work / "script.json"
    try:
        pre = PREWRITTEN / f"{a.lang}_{e['key']}.json"
        if a.reuse and sj.exists():
            d = json.loads(sj.read_text(encoding="utf-8")); s, chk = d["script"], d["check"]
        elif pre.exists():
            d = json.loads(pre.read_text(encoding="utf-8")); s, chk = d["script"], d["check"]
            print(f"[katha] prewritten script ({d.get('written')})")
        else:
            s, chk = write.write(e, a.lang, L, src)
    except RuntimeError as err:
        # Only a checker rejection is the story's fault. Before 2026-10-27 "all Gemini models/keys
        # exhausted" also landed here and retired good stories as failed_check.
        if not str(err).startswith("no script passed"):
            raise GeminiDown(err)
        raise StoryFailed(err)
    except Exception as err:                      # 429/5xx from the SDK
        raise GeminiDown(err)
    (work / "script.json").write_text(json.dumps(dict(script=s, check=chk), ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(s["sentences"]))
    if a.dry:
        return

    story_en = f"{e['key'].replace('_', ' ')} - " + "; ".join(s.get("claims_en", []))
    from PIL import Image
    sh = work / "shots.json"
    if a.reuse and sh.exists():
        shots = json.loads(sh.read_text(encoding="utf-8"))
        for i, c in enumerate(shots):
            c["img"] = Image.open(work / f"img_{i}.jpg")
    else:
        # Illustrated character scenes first (aiart.py, owner 2026-11-23); Wikimedia when it is off or fails.
        # NOT for English (Wait, That's Real?), from 2026-11-28: its AI-illustrated Shorts 11-24..11-28 got 2-63 views
        # each (median ~20), while its real-photo Shorts that month ran 300-3,000 (median ~700; the one photo
        # fallback in that week got 1,124). AI drawings of real people (Lincoln, Galileo) read as fake to that
        # audience. Ajab's te/ta AI Shorts held their photo-era range, so Indian languages keep the illustrations.
        import aiart
        use_ai = aiart.enabled() and a.lang != "en"
        shots = aiart.shots(s, e.get("kind"), a.lang, L["name"], story_en) if use_ai else None
        if not shots:
            shots = media.images(e, s.get("visuals"), story_en, need=8, lines=s["sentences"])
        for i, c in enumerate(shots):
            c["img"].save(work / f"img_{i}.jpg", quality=92)
        sh.write_text(json.dumps([{k: v for k, v in c.items() if k != "img"} for c in shots], ensure_ascii=False, indent=1), encoding="utf-8")
    if len(shots) < 3:
        raise StoryFailed(f"only {len(shots)} usable images")
    if e["key"] in festivals.keys_for(a.lang, dt.date.today()) and len(shots) < FEST_MIN_IMAGES:
        raise StoryFailed(f"festival story with only {len(shots)} usable images (need {FEST_MIN_IMAGES})")

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
    # Pause-anchored sentences first; Whisper word times drifted ~15 s on long hi/te narration.
    wt = media.sentence_word_times(s["sentences"], voice, D) or media.word_times(words, asr, D)
    total = D + 0.8
    job = dict(L=L, sentences=s["sentences"], word_times=wt, hook_text=s["hook_text"], kicker=s["kicker"],
               cta=s.get("cta"), subscribe=L["sub"], shots=[c["img"] for c in shots], voice=voice,
               line_shots=media.line_plan(shots, len(s["sentences"])) if any(c.get("lines") for c in shots) else None,
               music=story_music(e, total, work), duration=total,
               endcard="wtr" if a.lang == "en" else "ajab")     # like + subscribe sign-off (owner, 2026-10-28)
    t0 = time.time()
    mp4 = render.render(job, work / "short.mp4", work)
    print(f"[render] {mp4} in {time.time() - t0:.0f}s")

    tags = [h.lstrip("#").strip() for h in s.get("hashtags", [])]
    desc = s["description"] + "\n\n🔔 " + L["sub"] + "\n\n" + " ".join("#" + t.replace(" ", "") for t in tags[:5]) + "\n\n" + credits(sources, shots)
    meta = dict(title=s["title"], description=desc, tags=tags + ["shorts", L.get("channel", ("ajab gajab",))[0].lower(), L["name"]], lang=a.lang,
                comment=s["sentences"][-1] + "\n\n🔔 " + L["sub"],
                synthetic=any(c.get("ai") for c in shots))      # YouTube's altered/synthetic disclosure for AI art
    import ytcaptions
    meta["captions"] = ytcaptions.sentence_cues(s["sentences"], wt)
    (work / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.no_upload:
        return
    local = HERE.parent.parent / L["channel"][1] if L.get("channel") else HERE.parent / "CHANNEL_Ajab_Gajab_Facts_CONFIG.json"
    cfg = os.environ.get("CHANNEL_CONFIG") or local.read_text()
    vid = upload(mp4, meta, cfg)
    print(f"[upload] https://youtube.com/shorts/{vid}")
    # Same file to the Ajab Gajab Stories Facebook Page (katha/fb.py: slots 1 and 3 only, never raises).
    # The caption keeps the Wikimedia credits and drops YouTube's subscribe line.
    import fb
    fb.post_reel(mp4, s["title"] + "\n\n" + s["description"] + "\n\n"
                 + " ".join("#" + t.replace(" ", "") for t in tags[:5]) + "\n\n" + credits(sources, shots),
                 slot=a.slot, lang=a.lang)
    led = ledger()
    led.append(dict(key=e["key"], lang=a.lang, date=str(dt.date.today()), utc=dt.datetime.now(dt.timezone.utc).strftime("%H:%M"),
                    status="posted", video_id=vid, title=s["title"], seconds=round(total, 1),
                    slot=a.slot if a.slot >= 0 else None))
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    (PREWRITTEN / f"{a.lang}_{e['key']}.json").unlink(missing_ok=True)
    (BACKUP / f"{a.lang}_{e['key']}.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
