"""trends.py: stories picked because the audience is talking about them right now.

Owner 2026-11-14: "build the trend version for each channel ... post whats trending and are best bets". The
festival calendar (festivals.py) is fixed a month ahead and missed things like Kanda Sashti, the Tamil festival
that was No. 3 on Tamil Wikipedia on 11-13. The trend scout fills that gap. It is a daily Claude routine with web
search, run at about 00:20 UTC, that reads katha/trend_radar.json (radar.py) and researches each audience. It
then writes:
  - katha/bank_trend.json: one entry per pick, either a new story or an existing bank key told now
  - katha/prewritten/<lang>_<key>.json: the script, which Gemini checks when the push lands (prewrite.yml)

How it plugs in:
  - bank.py merges new trend stories into bank.S, so prewrite/backup/verify see them like any story.
  - make.pick: an active trend story for that language goes before festivals and everything else. Its script
    must be Gemini-verified first. If there is no script, Gemini writes one at post time with its usual check.
  - make.slot_lang: languages without a fixed slot that have an active trend story take the rotating slot 1,
    and slot 2 when no festival wants it. Kannada (slot 0), Telugu (slot 3) and English (WTR slots 4/5)
    pick their trend stories in their own slots.

Entry shape (new story):
  {"key": "tr_<slug>", "lang": "ta", "kind": "myth", "wiki": ["English Wikipedia title", ...],
   "art": ["Commons search", ...], "angle": "the one striking fact",
   "trend": {"why": "...", "signals": ["ta.wikipedia #3 Kanda Sashti Kavasam", ...], "until": "2026-11-16",
             "score": 9}, "added": "2026-11-14"}
An existing bank story only needs key, lang (the language to tell it in), trend and added.

    python katha/trends.py status         # active picks, posted or not, and today's slot languages
    python katha/trends.py bank <lang>    # unposted bank stories in a language (to reuse one)
    python katha/trends.py validate       # shape check (the routine runs it before pushing)
"""
import datetime as dt, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "bank_trend.json"
FROM = dt.date(2026, 11, 14)
LANG_CODES = {"kn", "te", "ta", "hi", "ml", "mr", "bn", "gu", "or", "pa", "en"}
KINDS = {"myth", "saint", "history", "people", "sport", "folk", "wonder", "engineering", "nature", "food",
         "space", "science", "place", "mystery", "art"}
MAX_DAYS = 4                     # a trend window longer than this is a calendar entry, not a trend


def load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def active(day=None):
    day = str(day or dt.date.today())
    return [e for e in load() if e.get("added", "") <= day <= (e.get("trend") or {}).get("until", "")]


def keys_for(lang, day=None):
    """Active trend story keys for `lang`, best score first."""
    es = sorted((e for e in active(day) if e.get("lang") == lang), key=lambda e: -e["trend"].get("score", 0))
    return list(dict.fromkeys(e["key"] for e in es))


def langs_for(day=None, done=frozenset()):
    """Languages with an active trend story not yet told (done = {(key, lang)}), best score first."""
    es = sorted(active(day), key=lambda e: -e["trend"].get("score", 0))
    return list(dict.fromkeys(e["lang"] for e in es if (e["key"], e["lang"]) not in done))


def validate():
    import bank
    keys = {s["key"] for s in bank.S}
    bad = []
    seen = set()
    for i, e in enumerate(load()):
        k, tr = e.get("key", ""), e.get("trend") or {}
        where = f"#{i} {k or '?'}"
        if (k, e.get("lang")) in seen:
            bad.append(f"{where}: duplicate key+lang")
        seen.add((k, e.get("lang")))
        if e.get("lang") not in LANG_CODES:
            bad.append(f"{where}: lang must be one of {sorted(LANG_CODES)}")
        if k not in keys:
            bad.append(f"{where}: not in bank.S (a new story needs kind, wiki, art, angle)")
        new = k.startswith("tr_")
        if new:
            if e.get("kind") not in KINDS:
                bad.append(f"{where}: kind must be one of {sorted(KINDS)}")
            if not e.get("wiki") or not all(isinstance(w, str) for w in e["wiki"]):
                bad.append(f"{where}: wiki must list English Wikipedia titles")
            if len(e.get("art") or []) < 2:
                bad.append(f"{where}: art needs at least 2 Commons search phrases")
            if not e.get("angle"):
                bad.append(f"{where}: angle missing")
        try:
            a, u = dt.date.fromisoformat(e["added"]), dt.date.fromisoformat(tr["until"])
            if not 0 <= (u - a).days <= MAX_DAYS:
                bad.append(f"{where}: until must be 0-{MAX_DAYS} days after added")
        except Exception:
            bad.append(f"{where}: added / trend.until must be YYYY-MM-DD")
        if not tr.get("why") or not tr.get("signals") or not isinstance(tr.get("score"), (int, float)):
            bad.append(f"{where}: trend needs why, signals and a numeric score")
    for b in bad:
        print("BAD", b)
    print("OK" if not bad else f"{len(bad)} problem(s)")
    return not bad


def status():
    import make
    today = dt.date.today()
    led = make.ledger()
    posted = {(r["key"], r["lang"]): r for r in led if r.get("status") == "posted"}
    for e in sorted(load(), key=lambda e: e.get("added", "")):
        if e.get("trend", {}).get("until", "") < str(today - dt.timedelta(days=3)):
            continue
        p = posted.get((e["key"], e["lang"]))
        pre = make.PREWRITTEN / f"{e['lang']}_{e['key']}.json"
        state = (f"POSTED {p['date']} slot {p.get('slot')} {p.get('video_id', '')}" if p else
                 ("script verified" if pre.exists() and make._verified(pre) else
                  "script waiting for Gemini" if pre.exists() else "no script yet"))
        print(f"{e['added']}..{e['trend']['until']}  {e['lang']} {e['key']:32} score {e['trend'].get('score')}  {state}")
    for day in (today, today + dt.timedelta(days=1)):
        print(f"{day} slot languages: " + ", ".join(f"{s}={make.slot_lang(s, day)}" for s in (0, 1, 2, 3))
              + "  (WTR slots 4/5 = en)")


def bank_list(lang):
    import bank, make
    done = {(r["key"], r["lang"]) for r in make.ledger() if r.get("status") in ("posted", "failed_check")}
    for s in bank.S:
        if s["lang"] in (lang, "all") and (s["key"], lang) not in done:
            print(f"{s['key']:28} {s['lang']:4} {s['kind']:12} {', '.join(s['wiki'])[:60]}  | {s.get('angle', '')[:80]}")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "validate":
        sys.exit(0 if validate() else 1)
    elif cmd == "bank":
        bank_list(sys.argv[2])
    else:
        status()
