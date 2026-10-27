"""Emergency script bank, filled weekly by a Claude routine (owner, 2026-10-27).

make.py writes with Gemini. On a day it can't (free quota spent, outage) it moves one of these
into katha/prewritten/ and posts that instead of failing. The stories are reserved: make.pick()
and prewrite.py skip them, so a backup is only spent on such a day.

Needs only the standard library + requests, so the routine runs it without the render stack.

    python katha/backup.py status            # stock per language, target, what to write next
    python katha/backup.py source <key>      # the English Wikipedia text a script may use
    python katha/backup.py validate          # shape + word-count check of every backup file
"""
import json, re, sys
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bank
from langs import LANGS

DIR = HERE / "backup"
# The fixed daily slots: Kannada slot 0, Hindi slot 2, Telugu slot 3, Strange But True (en).
TARGET = {"kn": 3, "te": 2, "hi": 2, "en": 2}
KEYS = ("title", "hook_text", "kicker", "sentences", "cta", "description", "hashtags", "visuals", "claims_en")


def _taken():
    led = json.loads((HERE / "ledger.json").read_text(encoding="utf-8"))
    taken = {(r["key"], r["lang"]) for r in led if r.get("status") in ("posted", "failed_check")}
    for d in (HERE / "prewritten", DIR):
        for p in d.glob("*.json"):
            lang, key = p.stem.split("_", 1)
            taken.add((key, lang))
    return taken


def candidates(lang, n):
    """Next unused stories: the language's own regional ones first, then pan-Indian (not for en)."""
    taken = _taken()
    regional = [s for s in bank.S if s["lang"] == lang and (s["key"], lang) not in taken]
    common = [s for s in bank.S if s["lang"] == "all" and (s["key"], lang) not in taken] if lang != "en" else []
    return (regional + common)[:n]


def status():
    have = {}
    for p in sorted(DIR.glob("*.json")):
        lang, key = p.stem.split("_", 1)
        have.setdefault(lang, []).append(key)
    for lang, want in TARGET.items():
        got = have.get(lang, [])
        need = max(0, want - len(got))
        nxt = [f"{s['key']} ({s['kind']}; angle: {s.get('angle') or '-'})" for s in candidates(lang, need)]
        print(f"{lang}: {len(got)}/{want} in stock {got}  write {need}: {nxt}")


def source(key):
    e = next(s for s in bank.S if s["key"] == key)
    for t in e["wiki"]:
        r = requests.get("https://en.wikipedia.org/w/api.php", params=dict(
            action="query", format="json", prop="extracts", explaintext=1, redirects=1, titles=t),
            headers={"User-Agent": "ajabgajab-katha-backup/1.0"}, timeout=30).json()
        p = list(r["query"]["pages"].values())[0]
        txt = re.sub(r"\n==+ (See also|References|External links|Notes|Further reading|Bibliography) ==+[\s\S]*", "",
                     p.get("extract", ""))
        print(f"### {p['title']}\n{txt[:14000]}\n")


def validate():
    bad = 0
    for p in sorted(DIR.glob("*.json")):
        lang, key = p.stem.split("_", 1)
        try:
            d = json.loads(p.read_text(encoding="utf-8")); s = d["script"]
            missing = [k for k in KEYS if k not in s]
            w0, w1 = LANGS[lang].get("words", (85, 110))
            n = len(" ".join(s["sentences"]).split())
            probs = ([f"missing {missing}"] if missing else []) + ([f"{n} words, need {w0}-{w1}"] if not w0 <= n <= w1 else []) \
                + ([] if 7 <= len(s["sentences"]) <= 9 else [f"{len(s['sentences'])} sentences, need 7-9"]) \
                + ([] if any(x["key"] == key for x in bank.S) else ["key not in bank.py"]) \
                + ([] if d.get("check", {}).get("ok") else ["check.ok is not true"])
        except Exception as ex:
            probs = [f"unreadable: {ex}"]
        print(f"{'OK ' if not probs else 'BAD'} {p.name} {probs}")
        bad += bool(probs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"status": status, "validate": validate}.get(cmd, lambda: source(sys.argv[2]))()
