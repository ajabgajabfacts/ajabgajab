"""radar.py: what each channel's audience is looking up right now. Free sources, no Gemini.

Owner 2026-11-14: "build the trend version for each channel ... post whats trending and are best bets on each
channel". This only gathers signals into katha/trend_radar.json. The daily trend scout (a Claude routine with
web search, ~00:20 UTC) reads it, researches further, and picks stories into katha/bank_trend.json
(trends.py).

  - Google Trends daily searches per Indian state (its language's audience), the US and the UK
  - Wikipedia's most-read articles yesterday on each language's Wikipedia; "new" = not in the day before's
    top 100. On 11-13 the top Hindi page was the Ramayana (2026) film and Tamil readers were on Kanda Sashti,
    a festival festivals.py did not have.
  - YouTube's most popular videos in India and the US (1 quota unit each; skipped without credentials)

    python katha/radar.py            # write katha/trend_radar.json
    python katha/radar.py --print    # also print a short digest
"""
import datetime as dt, json, os, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "trend_radar.json"
UA = "AjabGajabTrendRadar/1.0 (+https://github.com/ajabgajabfacts)"

GEOS = {"IN": "India", "IN-KA": "Karnataka (kn)", "IN-AP": "Andhra Pradesh (te)", "IN-TG": "Telangana (te)",
        "IN-TN": "Tamil Nadu (ta)", "IN-KL": "Kerala (ml)", "IN-MH": "Maharashtra (mr)", "IN-WB": "West Bengal (bn)",
        "IN-GJ": "Gujarat (gu)", "IN-OR": "Odisha (or)", "IN-PB": "Punjab (pa)", "IN-UP": "Uttar Pradesh (hi)",
        "IN-BR": "Bihar (hi)", "US": "United States (en)", "GB": "United Kingdom (en)"}
WIKIS = ["kn", "te", "ta", "hi", "ml", "mr", "bn", "gu", "or", "pa", "en"]
MAIN_PAGES = {"Main_Page", "मुखपृष्ठ", "ಮುಖ್ಯ_ಪುಟ", "మొదటి_పేజీ", "முதற்பக்கம்", "പ്രധാന_താൾ", "প্রধান_পাতা",
              "મુખપૃષ્ઠ", "ପ୍ରଧାନ_ପୃଷ୍ଠା", "ਮੁੱਖ_ਸਫ਼ਾ"}


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def google(geo):
    """Today's trending searches for one region: [{q, traffic, news: [headline, ...]}]."""
    root = ET.fromstring(_get(f"https://trends.google.com/trending/rss?geo={geo}"))
    out = []
    for it in root.iter("item"):
        news = [n.findtext("{*}news_item_title") for n in it.findall("{*}news_item")]
        out.append(dict(q=it.findtext("title"), traffic=it.findtext("{*}approx_traffic"),
                        news=[h for h in news if h][:3]))
    return out


def wiki_top(lang, day):
    url = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{lang}.wikipedia/all-access/"
           f"{day:%Y/%m/%d}")
    arts = json.loads(_get(url))["items"][0]["articles"]
    return [a for a in arts if ":" not in a["article"] and a["article"] not in MAIN_PAGES]


def wiki(lang, n=30):
    """Yesterday's most-read articles (UTC), marking those that were not in the day before's top 100."""
    y = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    try:
        top = wiki_top(lang, y)
    except Exception:                    # smaller wikis' daily list can land a day late (404)
        y -= dt.timedelta(days=1)
        top = wiki_top(lang, y)
    try:
        before = {a["article"] for a in wiki_top(lang, y - dt.timedelta(days=1))[:100]}
    except Exception:
        before = set()
    return [dict(title=a["article"].replace("_", " "), views=a["views"], new=a["article"] not in before, day=str(y))
            for a in top[:n]]


def youtube():
    """Titles of YouTube's most popular videos in India and the US, if channel credentials are available."""
    raw = os.environ.get("CHANNEL_CONFIG")
    p = HERE.parent / "CHANNEL_Ajab_Gajab_Facts_CONFIG.json"
    if not raw and p.exists():
        raw = p.read_text(encoding="utf-8")
    if not raw:
        return {}
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=Credentials.from_authorized_user_info(json.loads(raw)["credentials"]),
               cache_discovery=False)
    out = {}
    for region in ("IN", "US"):
        r = yt.videos().list(part="snippet,statistics", chart="mostPopular", regionCode=region, maxResults=30).execute()
        out[region] = [dict(title=v["snippet"]["title"], channel=v["snippet"]["channelTitle"],
                            views=int(v["statistics"].get("viewCount", 0))) for v in r.get("items", [])]
    return out


def collect():
    data = dict(generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), google={}, wiki={},
                youtube={}, errors=[])
    for geo, label in GEOS.items():
        try:
            data["google"][f"{geo} {label}"] = google(geo)
        except Exception as e:
            data["errors"].append(f"google {geo}: {str(e)[:120]}")
    for lang in WIKIS:
        try:
            data["wiki"][lang] = wiki(lang)
        except Exception as e:
            data["errors"].append(f"wiki {lang}: {str(e)[:120]}")
    try:
        data["youtube"] = youtube()
    except Exception as e:
        data["errors"].append(f"youtube: {str(e)[:120]}")
    return data


def digest(d):
    lines = [f"radar {d['generated']}  errors: {d['errors'] or 'none'}"]
    for k, v in d["google"].items():
        lines.append(f"[G {k}] " + ", ".join(x["q"] for x in v[:8]))
    for k, v in d["wiki"].items():
        lines.append(f"[W {k}] " + ", ".join(("*" if x["new"] else "") + x["title"] for x in v[:10]))
    for k, v in (d.get("youtube") or {}).items():
        lines.append(f"[YT {k}] " + " | ".join(x["title"][:50] for x in v[:8]))
    return "\n".join(lines)


if __name__ == "__main__":
    d = collect()
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[radar] wrote {OUT.name}: {len(d['google'])} regions, {len(d['wiki'])} wikis, "
          f"{sum(len(v) for v in d['youtube'].values())} YouTube titles, {len(d['errors'])} errors")
    if "--print" in sys.argv:
        print(digest(d))
