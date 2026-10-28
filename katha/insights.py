"""insights.py — learn from our own numbers, so the next Short is picked on evidence.

    python katha/insights.py            -> writes katha/insights.json + katha/INSIGHTS.md
    python katha/insights.py --print    -> also prints the summary

Built 2026-10-23 (owner: "use the insights to self-improve and post based on them").
Runs daily before slot 0 (insights.yml). make.py reads insights.json:
  - lang weights  -> which regional language the rotating slots 0 and 1 get
  - kind weights  -> which story type (myth / history / saint / wonder / folk) pick() favours
  - proven titles -> handed to the writer as style examples for that language
Format (length, structure, music) is deliberately NOT tuned here: the owner's 75 s experiment
lost to 35 s (memory ajab-short-length), so format changes stay a human decision. This file
only reports format findings in INSIGHTS.md.

Sources, all official APIs with the channel's own OAuth token (CLAUDE.md: no Studio scraping):
  Data API       videos.list statistics: real-time lifetime views (the score)
  Analytics API  per video: averageViewPercentage, averageViewDuration, subscribersGained, shares;
                 per channel: traffic sources, top search terms, related videos that send us views,
                 age/gender, countries; audienceRetention curves for the best and worst Shorts.
                 Analytics lags ~2-3 days, so a missing row means "not in yet", never "bad".
  Facebook       Reel `views` on the Ajab Gajab Stories Page (no read_insights grant, so no more).

Weights are shrunk toward 1.0 for small samples (PRIOR_N) and clamped to [FLOOR, CAP], so one
lucky video can't take over the rotation and every language/kind keeps getting tested.
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bank

LEDGER = HERE / "ledger.json"
OUT, MD = HERE / "insights.json", HERE / "INSIGHTS.md"
MATURE_H = 36            # a Short is still in its feed test before this (same as tools/yt_stats.py)
PRIOR_N = 3              # pseudo-samples at weight 1.0: 3 videos move a weight about halfway
FLOOR, CAP = 0.5, 2.5    # every option keeps >= half its fair share
MAX_LIFT = math.log(4)   # per-video cap on how far one Short moves its group
G = "https://graph.facebook.com/v23.0"
SINCE = "2026-10-19"     # the story format started here; older uploads were a different channel
# The rotating slots' languages and starting weights. Kannada starts at 2: the owner's 10-23 push
# (it appears twice in make.ROTATING). Data moves every weight from here. Kept here, not imported,
# so this job doesn't need make.py's render stack.
LANG_PRIOR = {"ta": 1.0, "kn": 2.0, "bn": 1.0, "mr": 1.0, "ml": 1.0, "gu": 1.0, "or": 1.0, "pa": 1.0}


def _creds(env, local):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    raw = os.environ.get(env) or (local.read_text() if local.exists() else "")
    if not raw:
        return None
    c = Credentials.from_authorized_user_info(json.loads(raw)["credentials"])
    if not c.valid:
        c.refresh(Request())
    return c


def _q(an, **kw):
    """One Analytics report as a list of dicts; [] on any failure (fail safe, see module doc)."""
    try:
        r = an.reports().query(ids="channel==MINE", startDate=SINCE, endDate=str(dt.date.today()), **kw).execute()
        cols = [h["name"] for h in r.get("columnHeaders", [])]
        return [dict(zip(cols, row)) for row in r.get("rows", [])]
    except Exception as e:
        print(f"[insights] analytics {kw.get('dimensions')}: {str(e)[:150]}")
        return []


def channel_data(creds, vids):
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    an = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    stats = {}
    for i in range(0, len(vids), 50):
        for v in yt.videos().list(part="statistics,snippet,status", id=",".join(vids[i:i + 50])).execute()["items"]:
            if v["status"]["privacyStatus"] == "public":
                stats[v["id"]] = dict(views=int(v["statistics"].get("viewCount", 0)),
                                      likes=int(v["statistics"].get("likeCount", 0)),
                                      comments=int(v["statistics"].get("commentCount", 0)),
                                      published=v["snippet"]["publishedAt"])
    per = {}
    for i in range(0, len(vids), 200):
        for r in _q(an, dimensions="video", filters="video==" + ",".join(vids[i:i + 200]),
                    metrics="views,averageViewPercentage,averageViewDuration,subscribersGained,shares", maxResults=200):
            per[r["video"]] = r
    ch = dict(
        traffic=_q(an, dimensions="insightTrafficSourceType", metrics="views", sort="-views"),
        searches=_q(an, dimensions="insightTrafficSourceDetail", filters="insightTrafficSourceType==YT_SEARCH",
                    metrics="views", sort="-views", maxResults=15),
        related=_q(an, dimensions="insightTrafficSourceDetail", filters="insightTrafficSourceType==RELATED_VIDEO",
                   metrics="views", sort="-views", maxResults=10),
        audience=_q(an, dimensions="ageGroup,gender", metrics="viewerPercentage"),
        countries=_q(an, dimensions="country", metrics="views", sort="-views", maxResults=8),
    )
    return yt, an, stats, per, ch


def retention(an, vid):
    """Share of viewers still watching at 10%, 50% and 90% of the Short (None if not in yet)."""
    rows = _q(an, dimensions="elapsedVideoTimeRatio", filters=f"video=={vid}", metrics="audienceWatchRatio")
    if not rows:
        return None
    pts = {round(float(r["elapsedVideoTimeRatio"]), 2): float(r["audienceWatchRatio"]) for r in rows}
    at = lambda x: pts.get(x) or pts[min(pts, key=lambda k: abs(k - x))]
    return {"10%": round(at(0.1), 2), "50%": round(at(0.5), 2), "90%": round(at(0.9), 2)}


def fb_views():
    """title -> Reel views on the Ajab Gajab Stories Page. katha/fb.py starts every caption with the title."""
    raw = os.environ.get("FB_PAGE_TOKEN") or ((HERE.parent / "fb_page_token.txt").read_text()
                                              if (HERE.parent / "fb_page_token.txt").exists() else "")
    if not raw:
        return {}
    cfg = json.loads(raw)
    try:
        r = requests.get(f"{G}/{cfg['page_id']}/video_reels", timeout=30, params={
            "fields": "description,views", "limit": 100, "access_token": cfg["page_token"]}).json()
        return {(v.get("description") or "").split("\n")[0].strip(): v.get("views", 0) for v in r.get("data", [])}
    except Exception as e:
        print(f"[insights] facebook: {str(e)[:150]}")
        return {}


def weights(rows, field, prior=None):
    """Shrunk geometric-mean lift of total views vs the channel median, per value of `field`."""
    med = statistics.median(r["total"] for r in rows) or 1
    groups = defaultdict(list)
    for r in rows:
        # One viral video counts as at most 4x (or 1/4x) the median, so a single outlier can't
        # max out a weight on its own (Mysore Palace at 139x took "engineering" to the cap).
        groups[r[field]].append(max(-MAX_LIFT, min(MAX_LIFT, math.log((r["total"] + 1) / (med + 1)))))
    out = {}
    for k in set(groups) | set(prior or {}):
        logs = groups.get(k, [])
        base = math.log((prior or {}).get(k, 1.0))
        w = math.exp((sum(logs) + PRIOR_N * base) / (len(logs) + PRIOR_N))
        out[k] = dict(w=round(min(CAP, max(FLOOR, w)), 2), n=len(logs),
                      median=int(statistics.median([r["total"] for r in rows if r[field] == k])) if logs else None)
    return out


def build(print_md=False):
    led = [r for r in json.loads(LEDGER.read_text(encoding="utf-8")) if r.get("status") == "posted" and r.get("video_id")]
    kind = {s["key"]: s["kind"] for s in bank.S}
    fb = fb_views()
    now = dt.datetime.now(dt.timezone.utc)
    result = {"updated": now.strftime("%Y-%m-%dT%H:%MZ"), "channels": {}}
    md = [f"# Insights ({result['updated']})", "",
          "Auto-written daily by katha/insights.py. Weights above 1 get picked more often; floor 0.5, cap 2.5.", ""]

    chans = [("ajab", "CHANNEL_CONFIG", HERE.parent / "CHANNEL_Ajab_Gajab_Facts_CONFIG.json", lambda r: r["lang"] != "en"),
             ("en", "CHANNEL_CONFIG_EN", HERE.parent.parent / "week_test/files/CHANNEL_Money_Sorted_AU_CONFIG.json",
              lambda r: r["lang"] == "en")]
    for name, env, local, keep in chans:
        mine = [r for r in led if keep(r)]
        creds = _creds(env, local) if mine else None
        if not creds:
            continue
        yt, an, stats, per, ch = channel_data(creds, [r["video_id"] for r in mine])
        rows = []
        for r in mine:
            s = stats.get(r["video_id"])
            if not s:
                continue
            age_h = (now - dt.datetime.fromisoformat(s["published"].replace("Z", "+00:00"))).total_seconds() / 3600
            a = per.get(r["video_id"], {})
            f = fb.get(r.get("title", "").strip()) if name == "ajab" else None
            rows.append(dict(video_id=r["video_id"], title=r.get("title", ""), key=r["key"], lang=r["lang"],
                             kind=kind.get(r["key"], "?"), seconds=r.get("seconds"), slot=r.get("slot"),
                             age_h=round(age_h), yt=s["views"], fb=f, total=s["views"] + (f or 0),
                             likes=s["likes"], comments=s["comments"],
                             avp=a.get("averageViewPercentage"), avd=a.get("averageViewDuration"),
                             subs=a.get("subscribersGained"), shares=a.get("shares")))
        mature = [r for r in rows if r["age_h"] >= MATURE_H]
        info = dict(videos=sorted(rows, key=lambda r: -r["total"]), channel=ch)
        if len(mature) >= 4:
            prior = LANG_PRIOR
            info["lang_weights"] = weights([r for r in mature if r["lang"] in prior], "lang", prior) if name == "ajab" else {}
            info["kind_weights"] = weights(mature, "kind")
            best = sorted(mature, key=lambda r: -r["total"])
            for r in best[:3] + best[-3:]:
                r["retention"] = retention(an, r["video_id"])
            info["proven_titles"] = {}
            for r in best:
                lst = info["proven_titles"].setdefault(r["lang"], [])
                if len(lst) < 3 and r["total"] >= statistics.median(x["total"] for x in mature):
                    lst.append(r["title"])
            info["median_views"] = int(statistics.median(r["total"] for r in mature))
        result["channels"][name] = info
        md += summary(name, info)

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    if print_md:
        print("\n".join(md))
    return result


def summary(name, info):
    title = {"ajab": "Ajab Gajab Facts", "en": "Wait, That's Real?"}[name]
    v = info["videos"]
    out = [f"## {title}", ""]
    if "median_views" not in info:
        return out + [f"- {len(v)} public Shorts; not enough mature ones (36 h+) to learn from yet.", ""]
    out.append(f"- Median Short: {info['median_views']} views (YouTube + Facebook), {len(v)} Shorts.")
    for label, key in (("Language", "lang_weights"), ("Story type", "kind_weights")):
        if info.get(key):
            parts = sorted(info[key].items(), key=lambda kv: -kv[1]["w"])
            out.append(f"- {label} weights: " + ", ".join(f"{k} {d['w']} (n={d['n']})" for k, d in parts))
    for r in v[:3]:
        ret = f", retention {r['retention']}" if r.get("retention") else ""
        avp = f", {r['avp']:.0f}% watched" if r.get("avp") is not None else ""
        fb = f" + FB {r['fb']}" if r.get("fb") else ""
        out.append(f"- Top: {r['title'][:60]} ({r['lang']}, {r['kind']}): {r['yt']}{fb} views{avp}{ret}")
    with_avp = [r for r in v if r.get("avp") is not None and r.get("seconds")]
    if len(with_avp) >= 6:
        short = [r["avp"] for r in with_avp if r["seconds"] <= 45]
        long_ = [r["avp"] for r in with_avp if r["seconds"] > 45]
        if short and long_:
            out.append(f"- Format (not auto-tuned): <=45 s Shorts {statistics.median(short):.0f}% watched vs "
                       f">45 s {statistics.median(long_):.0f}%.")
    ch = info["channel"]
    if ch["traffic"]:
        tot = sum(int(r["views"]) for r in ch["traffic"]) or 1
        out.append("- Views come from: " + ", ".join(
            f"{r['insightTrafficSourceType'].lower()} {100 * int(r['views']) / tot:.0f}%" for r in ch["traffic"][:4]))
    if ch["searches"]:
        out.append("- People searched: " + ", ".join(r["insightTrafficSourceDetail"] for r in ch["searches"][:8]))
    if ch["countries"]:
        out.append("- Countries: " + ", ".join(f"{r['country']} {r['views']}" for r in ch["countries"][:5]))
    if ch["audience"]:
        top = sorted(ch["audience"], key=lambda r: -float(r["viewerPercentage"]))[:3]
        out.append("- Audience: " + ", ".join(f"{r['gender'][0]} {r['ageGroup'][3:]} {float(r['viewerPercentage']):.0f}%" for r in top))
    return out + [""]


def load():
    """What make.py reads. {} when the file is missing or stale (> 4 days): fall back to the fixed rotation."""
    try:
        d = json.loads(OUT.read_text(encoding="utf-8"))
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(d["updated"].replace("Z", "+00:00"))
        return d if age < dt.timedelta(days=4) else {}
    except Exception:
        return {}


if __name__ == "__main__":
    build(print_md="--print" in sys.argv)
