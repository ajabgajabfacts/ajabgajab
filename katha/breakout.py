"""breakout.py: spot a Short that is taking off, tell the owner, and double down while YouTube still pushes it.

Owner 2026-11-23: the bet is won by ANY payout, with no deadline. The only Ajab Shorts that ever broke out
(Mysore Dasara, 89k and 28k, 10-21/22) came in a cluster, and nothing followed them up while the feed was
warm. Owner chose "just notify me": no recording step, every follow-up uses the normal AI voice.

Every 3 h (breakout.yml):
  - real-time views (Data API) of every Ajab + WTR Short posted in the last WINDOW_H hours (from ledger.json)
  - a Short at >= THRESHOLD views is a breakout. It is recorded in katha/breakouts.json and the owner gets a
    GitHub issue (email + GitHub app). Each milestone it passes later (10k, 50k, ...) adds a comment.
  - the trend scout routine (~00:20 UTC) runs `breakout.py status`. For each breakout marked WANTS FOLLOW-UP,
    it writes a different story in the same language and theme as a trend entry (score 10) tagged
    trend.followup_of = <video_id>, so make.pick serves it first in that language's slot. The follow-up count
    is read from those tags in bank_trend.json, so each file keeps a single writer (this job writes
    breakouts.json, the scout writes bank_trend.json).

    python katha/breakout.py           # check, update breakouts.json, open/comment issues (needs GH_TOKEN in CI)
    python katha/breakout.py status    # what is on file and which breakouts still want follow-ups
"""
import datetime as dt, json, os, sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
LEDGER = HERE / "ledger.json"
FILE = HERE / "breakouts.json"
THRESHOLD = 3_000        # our best non-festival Short ever was ~1.9k (Ajab) / ~3k (WTR, lifetime)
WINDOW_H = 72            # only young Shorts: an old one creeping past 3k is not "taking off"
FOLLOWUP_DAYS = 4        # follow-ups are only worth writing while the original is still being served
MAX_FOLLOWUPS = 2
MILESTONES = [10_000, 50_000, 100_000, 500_000, 1_000_000, 3_000_000]
CHANNELS = [  # (name, env var with the OAuth config, local file, which ledger rows)
    ("Ajab Gajab", "CHANNEL_CONFIG", HERE.parent / "CHANNEL_Ajab_Gajab_Facts_CONFIG.json", lambda r: r["lang"] != "en"),
    ("Wait, That's Real?", "CHANNEL_CONFIG_EN",
     HERE.parent.parent / "week_test/files/CHANNEL_Money_Sorted_AU_CONFIG.json", lambda r: r["lang"] == "en"),
]


def load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(d):
    FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def followups(vid):
    """Keys of the trend entries the scout wrote as follow-ups to this video (trend.followup_of)."""
    try:
        rows = json.loads((HERE / "bank_trend.json").read_text(encoding="utf-8"))
    except Exception:
        rows = []
    return [e["key"] for e in rows if (e.get("trend") or {}).get("followup_of") == vid]


def wants_followup(vid, b, today=None):
    """True while a breakout is young enough to follow up and has fewer than MAX_FOLLOWUPS follow-ups."""
    today = today or dt.date.today()
    return (len(followups(vid)) < MAX_FOLLOWUPS
            and (today - dt.date.fromisoformat(b["found"][:10])).days < FOLLOWUP_DAYS)


def _views(creds, ids):
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    out = {}
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="statistics,snippet", id=",".join(ids[i:i + 50])).execute().get("items", []):
            out[v["id"]] = (int(v["statistics"].get("viewCount", 0)), v["snippet"]["publishedAt"])
    return out


def _gh(method, path, **body):
    """GitHub REST call with the workflow token; a no-op (prints) outside CI so local runs never post."""
    tok, repo = os.environ.get("GH_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (tok and repo):
        print(f"[breakout] (local, not sent) {method} {path}: {body.get('title') or body.get('body', '')[:80]}")
        return {}
    r = requests.request(method, f"https://api.github.com/repos/{repo}{path}", json=body, timeout=30,
                         headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
    if r.status_code >= 300:
        print(f"[breakout] GitHub {method} {path}: {r.status_code} {r.text[:200]}")
        return {}
    return r.json()


def check():
    from insights import _creds
    led = [r for r in json.loads(LEDGER.read_text(encoding="utf-8")) if r.get("status") == "posted" and r.get("video_id")]
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(hours=WINDOW_H + 24)).date().isoformat()     # ledger date is UTC post date
    known = load()
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    for name, env, local, keep in CHANNELS:
        mine = [r for r in led if keep(r) and r.get("date", "") >= cutoff]
        if not mine:
            continue
        creds = _creds(env, local)
        if not creds:
            print(f"[breakout] {name}: no credentials"); continue
        stats = _views(creds, [r["video_id"] for r in mine])
        for r in mine:
            vid = r["video_id"]
            if vid not in stats:
                continue
            views, published = stats[vid]
            age_h = (now - dt.datetime.fromisoformat(published.replace("Z", "+00:00"))).total_seconds() / 3600
            b = known.get(vid)
            if b:                                                    # already a breakout: milestones only
                b["views"] = views
                for m in MILESTONES:
                    if views >= m and m not in b.setdefault("milestones", []):
                        b["milestones"].append(m)
                        if b.get("issue"):
                            _gh("POST", f"/issues/{b['issue']}/comments",
                                body=f"Now **{views:,} views** after {age_h:.0f} h (passed {m:,}).")
                continue
            if views < THRESHOLD or age_h > WINDOW_H:
                continue
            b = dict(video_id=vid, channel=name, key=r["key"], lang=r["lang"], title=r.get("title", ""),
                     posted=published, found=now.strftime("%Y-%m-%dT%H:%MZ"), views=views,
                     views_at_found=views, age_h_at_found=round(age_h, 1),
                     milestones=[m for m in MILESTONES if views >= m])
            body = (f"{'@' + owner + ' ' if owner else ''}**{name}** Short is taking off: **{views:,} views in "
                    f"{age_h:.0f} h** (our usual is ~100-1,000).\n\nhttps://youtube.com/shorts/{vid}\n\n"
                    f"Story `{r['key']}` ({r['lang']}). The trend scout will write up to {MAX_FOLLOWUPS} follow-up "
                    f"stories in the same language and theme at its next run (~00:20 UTC). They post first in "
                    f"that language's slot with the normal AI voice. Nothing for you to do; this issue gets a "
                    f"comment at each milestone ({', '.join(f'{m:,}' for m in MILESTONES)}).")
            issue = _gh("POST", "/issues", title=f"Breakout: {r.get('title', vid)[:70]} ({views:,} views in {age_h:.0f} h)",
                        body=body)
            b["issue"] = issue.get("number")
            known[vid] = b
            print(f"[breakout] NEW {name} {vid} {views:,} views in {age_h:.0f} h: {r.get('title', '')}")
    save(known)
    return known


def status():
    d = load()
    if not d:
        print("no breakouts on file"); return
    for vid, b in sorted(d.items(), key=lambda kv: kv[1]["found"]):
        flag = "WANTS FOLLOW-UP" if wants_followup(vid, b) else ""
        print(f"{b['found'][:10]} {b['lang']} {b['views']:>9,} {vid} {b['key']:<28} follow-ups={followups(vid)} {flag}")


if __name__ == "__main__":
    status() if sys.argv[1:] == ["status"] else check()
