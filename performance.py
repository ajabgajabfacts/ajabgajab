# -*- coding: utf-8 -*-
"""Performance feedback loop: snapshot per-video stats each run and turn them
into topic-selection weights. The Shorts feed is a test-and-escalate loop —
views at 48h+ tell us whether a topic survived the swipe test, so the topic
chooser should learn from results instead of picking uniformly at random.

Data flow: upload stores video_id in topic_ledger.json -> refresh_performance()
(called at the start of every posting run) fetches stats for those ids and
writes performance.json (committed with the ledgers) -> pick_animation_type()
weights its pool by category track record and retires topics that died."""
import datetime, json, math
from pathlib import Path

from shared import load_topic_ledger
from charts import QUIZZES as TOPICS

PERF_PATH      = Path("performance.json")
MATURITY_HOURS = 48    # before this a video is still in YouTube's test window
MIN_SAMPLES    = 2     # matured videos a category needs before its weight moves
WEIGHT_FLOOR, WEIGHT_CAP = 0.25, 4.0

# Retirement is permanent, so it must be driven by evidence the AUDIENCE rejected
# a topic — not by evidence the feed never showed it. Low views alone cannot tell
# those apart: "never distributed" and "distributed and hated" both look like a
# small number. Judging on views retired this channel's two BEST topics
# (flags_countries at 3 views / 95.2% watched, tech_history at 4 / 98.4%) while
# sparing its worst (WYR: 277 views but only ~25% watched). Retention is the
# signal that separates them.
SIGNAL_VIEWS   = 50    # below this the feed never really tested it — no signal, no verdict
DEAD_RETENTION = 35.0  # avg % watched below this, WITH real views = genuinely rejected

_KEY_TO_CATEGORY = {t["key"]: t.get("concept", "misc") for t in TOPICS}


def _fetch_retention(analytics, ids: list) -> dict:
    """video_id -> averageViewPercentage, from the YouTube Analytics API.

    This is the ONLY thing that can retire a topic (see retired_keys), so it must
    fail safe: the Analytics API lags the Data API by ~2 days and needs both the
    yt-analytics.readonly scope AND the API enabled in that channel's Cloud
    project. A missing value therefore means "no verdict yet" — never "bad" — and
    an outright failure retires nothing at all."""
    if not analytics or not ids:
        return {}
    try:
        end   = datetime.date.today()
        start = end - datetime.timedelta(days=365)
        resp = analytics.reports().query(
            ids="channel==MINE",
            startDate=start.isoformat(), endDate=end.isoformat(),
            metrics="averageViewPercentage", dimensions="video",
            filters="video==" + ",".join(ids[:400]), maxResults=400,
        ).execute()
        pct = {row[0]: float(row[1]) for row in resp.get("rows", [])}
        print(f"[Perf] Retention: {len(pct)}/{len(ids)} videos have data "
              f"(the rest are younger than the ~2d reporting lag).")
        return pct
    except Exception as e:
        print(f"[Perf] Retention unavailable ({type(e).__name__}: {str(e)[:70]}) — "
              "no topic will be retired this run.")
        return {}


def refresh_performance(yt, analytics=None) -> None:
    """Fetch stats for every ledger entry that has a video_id; write PERF_PATH.
    Cheap (1 quota unit per 50 videos). Callers must treat failures as
    non-fatal — posting always beats measuring."""
    ledger = [e for e in load_topic_ledger() if e.get("video_id")]
    if not ledger:
        print("[Perf] No ledger entries with video_id yet — skipping snapshot.")
        return
    ids, stats = [e["video_id"] for e in ledger], {}
    for i in range(0, len(ids), 50):
        resp = yt.videos().list(part="statistics,snippet",
                                id=",".join(ids[i:i + 50])).execute()
        for item in resp.get("items", []):
            stats[item["id"]] = item
    retention = _fetch_retention(analytics, ids)
    now, rows = datetime.datetime.now(datetime.timezone.utc), []
    for e in ledger:
        item = stats.get(e["video_id"])
        if not item:
            continue  # deleted/private — drop from the snapshot
        s = item.get("statistics", {})
        rows.append({
            "video_id":     e["video_id"],
            "key":          e.get("concept", ""),
            "title":        e.get("title", ""),
            "published":    item["snippet"].get("publishedAt", ""),
            "views":        int(s.get("viewCount", 0)),
            "likes":        int(s.get("likeCount", 0)),
            "comments":     int(s.get("commentCount", 0)),
            "avg_view_pct": retention.get(e["video_id"]),  # None = no verdict yet
            "fetched":      now.isoformat(timespec="seconds"),
        })
    PERF_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"[Perf] Snapshot: {len(rows)} videos refreshed.")


def _matured_rows() -> list:
    try:
        rows = json.loads(PERF_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    now, out = datetime.datetime.now(datetime.timezone.utc), []
    for r in rows:
        try:
            pub = datetime.datetime.fromisoformat(r["published"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if now - pub >= datetime.timedelta(hours=MATURITY_HOURS):
            out.append(r)
    return out


def category_weights() -> dict:
    """Category -> selection weight, from matured videos only. Score is
    log10(views): a category one decade above the channel mean gets ~2.7x,
    one below ~0.37x, clamped to [0.25, 4]. Categories with too few matured
    videos keep weight 1.0 — unproven is not the same as bad (exploration)."""
    scores = {}
    for r in _matured_rows():
        cat = _KEY_TO_CATEGORY.get(r["key"])
        if cat:
            scores.setdefault(cat, []).append(math.log10(r["views"] + 1))
    all_scores = [s for v in scores.values() for s in v]
    if not all_scores:
        return {}
    mean = sum(all_scores) / len(all_scores)
    weights = {}
    for cat, vals in scores.items():
        if len(vals) >= MIN_SAMPLES:
            w = math.exp(sum(vals) / len(vals) - mean)
            weights[cat] = min(WEIGHT_CAP, max(WEIGHT_FLOOR, w))
    return weights


def retired_keys() -> set:
    """Topics the AUDIENCE rejected: enough views to count as a real test, but
    viewers swiped away. Never repeat them.

    Retirement needs positive evidence. A topic with few views was not rejected —
    it was never shown, and killing it forever on that basis throws away good
    content (see SIGNAL_VIEWS above). `avg_view_pct` comes from the YouTube
    Analytics API; while it is absent NOTHING is retired, which is the correct
    default — the soft category weighting still steers topic choice on its own.

    US-anchored topics are exempt: they target a smaller US-skewed audience on
    purpose, so judging them on raw global numbers would retire the geo tilt
    before it can pay off."""
    try:
        from charts import US_KEYS
    except Exception:
        US_KEYS = set()
    dead = set()
    for r in _matured_rows():
        pct = r.get("avg_view_pct")
        if (r["key"] and r["key"] not in US_KEYS
                and pct is not None
                and r["views"] >= SIGNAL_VIEWS
                and float(pct) < DEAD_RETENTION):
            dead.add(r["key"])
    return dead


# Deliberate topic tilt, multiplied on top of the data-driven category weights.
# Movies is the channel's first breakout ("3 Idiots" reel, 280 views on 2026-07-20)
# and the audience signal so far is Bollywood; this steers the rotation toward it
# without waiting for enough matured videos to move category_weights on its own.
# It COMPOSES with the live weighting — if movies proves out the data amplifies it
# further, if it fades the data pulls it back. Set to 1.0 to remove the tilt.
_MANUAL_BOOST = {"movies": 2.0}


def weight_for_key(key: str, weights: dict) -> float:
    cat = _KEY_TO_CATEGORY.get(key, "")
    return weights.get(cat, 1.0) * _MANUAL_BOOST.get(cat, 1.0)
