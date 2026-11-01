"""Daily story-idea feed for Wait, That's Real? (2026-11-01, owner approved).

WTR posts two English Shorts a day and its hand-built bank (bank.py, lang "en") empties in about a month.
This finds new strange-but-true candidates every day and adds the best few to bank_feed.json, which bank.py
merges in as ordinary "en" entries, so the Claude prewrite routine and make.py pick them up like any other.

Sources (no API keys):
  - Wikipedia:Unusual articles   the community's own list of strange-but-real topics (sampled daily)
  - Wikimedia featured feed      yesterday's most-read articles + "On this day" events
  (r/todayilearned was considered and left out, owner 2026-11-01: Reddit blocks unauthenticated requests,
   its API needs a registered app with commercial-use limits, and TIL mostly links Wikipedia anyway.)

Filters, in order (cheap first):
  already in the bank / already seen -> not a standard article -> under 12k bytes (too little to source a
  script from) -> Living people (bank rule) -> fewer than 4 Commons images for its title (WTR is all
  archival images) -> one Gemini call scores the survivors for "wait, that's real?" and family safety.
Only score >= 8, safe, non-sensitive candidates are added; at most MAX_ADD a day.

    python katha/feed.py             # run (writes bank_feed.json, feed_seen.json)
    python katha/feed.py --dry       # print what it would add
"""
import argparse, datetime as dt, json, random, re, sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ai, bank, media

FEED = HERE / "bank_feed.json"
SEEN = HERE / "feed_seen.json"
MAX_ADD = 4            # WTR uses 2 a day; 4 grows the bank without flooding it
MIN_BYTES = 12000
MAX_BYTES = 120000     # "Human", "World War I", "19th century": survey articles, not stories
UNUSUAL_SAMPLE = 25
KINDS = ["history", "science", "nature", "animal", "space", "engineering", "food", "sport", "record",
         "people", "folk", "wonder"]

SCORE = """You pick stories for "Wait, That's Real?", a YouTube Shorts channel of strange but TRUE stories
told in 35 seconds from Wikipedia (archival photos, calm narrator). Viewers are worldwide adults.

Score each candidate 1-10 for how strongly a viewer would think "wait, that's real?" AND keep watching:
a concrete, surprising event, person, place or object with a clear story spine. Low scores: dry topics,
lists, abstract concepts, ongoing politics, anything whose interest is only a statistic.

Also mark:
- safe: false if the core story is gore, sexual content, suicide, abuse of children, or cruelty played for shock.
- sensitive: true if it is a live political, ethnic or religious dispute, or mainly about a recent tragedy
  (last 30 years) with victims.
- kind: one of {kinds}
- angle: ONE plain sentence, under 20 words, the surprising spine of the story, stated as fact from the
  extract (no "did you know", no hype words).
- art: two Wikimedia Commons search phrases for real photos of it, most specific first.

Candidates:
{items}

Return JSON: {{"results": [{{"title": "...", "score": 0, "safe": true, "sensitive": false, "kind": "...",
"angle": "...", "art": ["...", "..."]}}]}} with one result per candidate, titles exactly as given."""


def _load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def wiki_api(**params):
    return media._get_json("https://en.wikipedia.org/w/api.php", dict(format="json", **params))


# ── Sources ─────────────────────────────────────────────────────────────────
def unusual(rng):
    titles = []
    for page in ["Wikipedia:Unusual articles"] + [f"Wikipedia:Unusual articles/{s}" for s in (
            "Places and infrastructure", "Biology", "History", "Science and technology", "Society and culture")]:
        try:
            r = wiki_api(action="parse", page=page, prop="links", redirects=1)
            titles += [l["*"] for l in r.get("parse", {}).get("links", []) if l.get("ns") == 0 and l.get("exists") is not None]
        except Exception as e:
            print(f"[feed] {page}: {str(e)[:80]}")
    titles = sorted(set(titles))
    rng.shuffle(titles)
    print(f"[feed] unusual articles: {len(titles)} listed")
    return titles


def featured(day):
    """(on-this-day pages, most-read pages). Most-read is mostly celebrities and news, so it goes last."""
    otd, top = [], []
    try:
        r = media._get_json(f"https://api.wikimedia.org/feed/v1/wikipedia/en/featured/{day:%Y/%m/%d}", {})
        top = [a["normalizedtitle"] for a in (r.get("mostread", {}) or {}).get("articles", [])[:10]]
        for ev in r.get("onthisday", []) or []:
            otd += [p["normalizedtitle"] for p in ev.get("pages", [])[:2]]
    except Exception as e:
        print(f"[feed] featured feed: {str(e)[:80]}")
    print(f"[feed] featured feed: {len(otd)} on this day, {len(top)} most read")
    return otd, top



# ── Filters ─────────────────────────────────────────────────────────────────
def details(titles):
    """title -> dict(title, length, living, extract, description) for standard articles (50 per call)."""
    out, resolved = {}, {}
    for i in range(0, len(titles), 50):
        r = wiki_api(action="query", titles="|".join(titles[i:i + 50]), redirects=1,
                     prop="info|categories|extracts|description|pageprops", clcategories="Category:Living people",
                     exintro=1, explaintext=1, exlimit="max", ppprop="disambiguation")
        q = r.get("query", {})
        for m in q.get("normalized", []) + q.get("redirects", []):
            resolved[m["from"]] = m["to"]
        for x in list(resolved):                    # normalized then redirected: follow the chain
            for _ in range(3):
                resolved[x] = resolved.get(resolved[x], resolved[x])
        for p in (q.get("pages", {}) or {}).values():
            if "missing" in p or p.get("ns") != 0 or "disambiguation" in p.get("pageprops", {}):
                continue
            out[p["title"]] = dict(title=p["title"], length=p.get("length", 0), living=bool(p.get("categories")),
                                   extract=(p.get("extract") or "")[:700], description=p.get("description", ""))
    return out, resolved


def has_images(title, need=4):
    try:
        return len(media.commons(title, limit=10)) >= need
    except Exception:
        return False


def slug(title):
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", title.lower())).strip("_")[:40]


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    today = dt.date.today()
    rng = random.Random(str(today))
    feed, seen = _load(FEED, []), set(_load(SEEN, []))
    have_titles = {t.lower() for s in bank.S for t in s["wiki"]}
    have_keys = {s["key"] for s in bank.S}

    otd, top = featured(today - dt.timedelta(days=1))
    fresh = lambda ts: [t for t in dict.fromkeys(ts) if t.lower() not in have_titles and t not in seen
                        and not re.match(r"(List of|Deaths in|\d{4} in )", t)]
    # filter BEFORE sampling, so a rerun on the same day (same shuffle) still gets unseen titles
    pool = fresh(fresh(unusual(rng))[:UNUSUAL_SAMPLE * 3] + otd + top)
    info, resolved = details(pool[:150])
    seen |= set(pool[:150])
    cands = []
    for t in dict.fromkeys(resolved.get(x, x) for x in pool[:150]):   # source order: Unusual articles first
        d = info.get(t)
        if not d or d["living"] or not MIN_BYTES <= d["length"] <= MAX_BYTES or t.lower() in have_titles:
            continue
        cands.append(d)
    print(f"[feed] {len(pool)} new titles -> {len(info)} articles -> {len(cands)} long enough, no living people")
    cands = cands[:40]
    cands = [d for d in cands if has_images(d["title"])]
    print(f"[feed] {len(cands)} with enough Commons images")
    if not cands:
        SEEN.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=0), encoding="utf-8") if not a.dry else None
        return
    items = "\n".join(f"- {d['title']} ({d['description']}): {d['extract'][:500]}" for d in cands)
    res = ai.json_call(SCORE.format(kinds=", ".join(KINDS), items=items), temperature=0.3).get("results", [])
    by = {d["title"]: d for d in cands}
    for r in res:
        if r.get("kind") not in KINDS:
            r["kind"] = "history"
    good = sorted([r for r in res if r.get("title") in by and r.get("score", 0) >= 8 and r.get("safe") is not False
                   and not r.get("sensitive") and r.get("angle")],
                  key=lambda r: -r["score"])
    added = []
    for r in good[:MAX_ADD]:
        key = slug(r["title"])
        if key in have_keys:
            key = (key + "_wtr")[:44]
        art = [x for x in (r.get("art") or []) if isinstance(x, str)][:2] or [r["title"]]
        added.append(dict(key=key, lang="en", kind=r["kind"], wiki=[r["title"]], art=art + [r["title"]],
                          angle=r["angle"].strip(), score=r["score"], added=str(today)))
    for r in res:
        print(f"  {r.get('score', '?'):>2} {'+' if any(x['wiki'][0] == r.get('title') for x in added) else ' '} "
              f"{r.get('title', '')[:50]:<50} {r.get('angle', '')[:70]}")
    if a.dry:
        print(json.dumps(added, ensure_ascii=False, indent=1)); return
    FEED.write_text(json.dumps(feed + added, ensure_ascii=False, indent=1), encoding="utf-8")
    SEEN.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"[feed] added {len(added)}: {', '.join(x['key'] for x in added)}")


if __name__ == "__main__":
    main()
