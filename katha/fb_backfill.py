"""fb_backfill.py — seed the Ajab Gajab Stories Facebook Page with our best Shorts first.

Owner, 2026-10-25: after two days the Page had 0 followers and its Reels 0 views, because
the slot 1/3 cross-posts were small-audience languages (or, te, gu). Same plan as
quizora/fb_backfill.py: the proven Shorts go first (Mysore Palace kn, 62k YouTube views).

Each Short is RE-RENDERED (make.py --key --no-upload): the CI work dirs of the originals are
gone, and the pre-10-23 ones carry Audio Library music that is licensed for YouTube only.
The script is rewritten for the same story; the caption keeps the YouTube title, which is
what insights.py matches FB Reel views on. Nothing goes to YouTube and the ledger is untouched.

    python katha/fb_backfill.py build     # rank posted Shorts by views -> fb_backfill.json (local, needs the config)
    python katha/fb_backfill.py next      # render + post the next queued one (respects fb.py's cap)
    python katha/fb_backfill.py status

While anything is queued, fb.py skips the pipeline's own slot 1/3 cross-post.
"""
import json, os, subprocess, sys, tempfile, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUEUE = HERE / "fb_backfill.json"
MIN_VIEWS = 500
# 2026-10-26 (owner): skip the backfill on long-form days. Each re-render costs ~7 Gemini calls and a
# long-form ~50; on Sunday 10-25 together they spent the free quota by 16:42 UTC, and the Hindi,
# Telugu and Strange But True Shorts after that all failed. Gemini's day starts at Pacific midnight
# (07:00 UTC in PDT, 08:00 in PST; every backfill cron lands on the same day either way).
LONG_DAYS = (6, 2)   # Sunday, Wednesday - keep in sync with katha_long.yml


def long_form_day(now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return (now - datetime.timedelta(hours=7)).weekday() in LONG_DAYS


def load():
    return json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else []


def save(q):
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")


def pending():
    return [x for x in load() if x["status"] == "queued"]


def build():
    from googleapiclient.discovery import build as gbuild
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    import requests
    sys.path.insert(0, str(HERE))
    import fb

    raw = os.environ.get("CHANNEL_CONFIG") or (HERE.parent / "CHANNEL_Ajab_Gajab_Facts_CONFIG.json").read_text(encoding="utf-8")
    creds = Credentials.from_authorized_user_info(json.loads(raw)["credentials"])
    if not creds.valid:
        creds.refresh(Request())
    yt = gbuild("youtube", "v3", credentials=creds)
    led = [r for r in json.loads((HERE / "ledger.json").read_text(encoding="utf-8"))
           if r.get("status") == "posted" and r["lang"] != "en" and r.get("video_id")]
    vids = []
    for i in range(0, len(led), 50):
        vids += yt.videos().list(part="snippet,statistics,status", id=",".join(r["video_id"] for r in led[i:i + 50])).execute()["items"]

    cfg = fb._cfg()
    r = requests.get(f"{fb.G}/{cfg['page_id']}/video_reels",
                     params={"fields": "description", "limit": 100, "access_token": cfg["page_token"]}, timeout=30)
    r.raise_for_status()
    on_fb = {(v.get("description") or "").split("\n")[0].strip() for v in r.json().get("data", [])}

    q = load()
    seen = {(x["key"], x["lang"]) for x in q}
    for v in sorted(vids, key=lambda v: -int(v["statistics"].get("viewCount", 0))):
        views, title = int(v["statistics"].get("viewCount", 0)), v["snippet"]["title"].strip()
        row = next(r for r in led if r["video_id"] == v["id"])
        k = (row["key"], row["lang"])
        if views < MIN_VIEWS or v["status"]["privacyStatus"] != "public" or title in on_fb or k in seen:
            continue
        seen.add(k)
        q.append(dict(video_id=v["id"], views=views, key=row["key"], lang=row["lang"], title=title, status="queued"))
    save(q)
    print(f"{len(pending())} queued of {len(q)}")


def next_one():
    sys.path.insert(0, str(HERE))
    import fb
    if long_form_day() and not os.environ.get("FORCE_BACKFILL"):
        print("[backfill] long-form day - leaving the Gemini quota to the Shorts and the long-form"); return
    q = load()
    item = next((x for x in q if x["status"] == "queued"), None)
    if not item:
        print("[backfill] queue empty"); return
    cfg = fb._cfg()
    if cfg and fb.posted_today(cfg) >= fb.MAX_PER_DAY:
        print("[backfill] daily cap reached - nothing to do"); return
    out = Path(tempfile.mkdtemp(prefix="fbb_"))
    print(f"[backfill] rendering {item['lang']}/{item['key']} ({item['views']} YouTube views): {item['title']}")
    r = subprocess.run([sys.executable, str(HERE / "make.py"), "--lang", item["lang"], "--key", item["key"],
                        "--no-upload", "--out", str(out)])
    work = next(out.glob(f"*_{item['lang']}_{item['key']}"), None)
    if r.returncode or not work or not (work / "short.mp4").exists() or not (work / "meta.json").exists():
        item["status"] = "render_failed"; save(q)
        raise SystemExit(f"[backfill] render failed for {item['key']}/{item['lang']}")
    meta = json.loads((work / "meta.json").read_text(encoding="utf-8"))
    # make.py's description = text, 🔔 subscribe, hashtags, credits; Facebook drops the YouTube subscribe line.
    body = "\n\n".join(p for p in meta["description"].split("\n\n") if not p.startswith("🔔"))
    fid = fb.post_reel(str(work / "short.mp4"), item["title"] + "\n\n" + body, lang=item["lang"], backfill=True)
    if fid:
        item.update(status="posted", fb_id=fid, at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"))
    save(q)
    print(f"[backfill] {'posted ' + fid if fid else 'not posted - stays queued'}; {len(pending())} left")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "build":
        build()
    elif cmd == "next":
        next_one()
    else:
        for x in load():
            print(f"{x['status']:<13} {x['views']:>6}  {x['lang']}/{x['key']}  {x['title'][:60]}")
