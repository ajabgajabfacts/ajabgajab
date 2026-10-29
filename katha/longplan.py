"""Claude-written long-forms (experiment, owner 2026-10-29): what to write, and a validator.

The daily Claude routine writes the next long-form a day or two ahead into
katha/prewritten_long/<lang>_<YYYY-MM-DD>.json. On the day, longform.py runs Gemini's CHECK once per chapter
(about 7 calls instead of about 50 to write it) and rewrites only a chapter that fails. The ledger marks the
video by="claude" so it can be compared with the Gemini-written ones.

    python katha/longplan.py --json      # long-forms due in the next 3 days with no file yet (the routine reads it)
    python katha/longplan.py validate    # check every file in prewritten_long/

File shape:
    {"lang": "hi", "date": "2026-11-01", "collection": "marvels", "by": "claude-routine", "written": "...",
     "chapters": [{"key": "<bank key>", "script": {"title", "hook_text", "kicker", "sentences", "visuals", "claims_en"}}],
     "frame": {the FRAME fields in longcollections.py: title, intro, outro, thumb_text, kicker, chapter_word,
               intro_label, outro_label, subscribe, description, hashtags}}
"""
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bank
from langs import LANGS
from longcollections import COLLECTIONS, FRAME, ledger, pick_collection

DIR = HERE / "prewritten_long"
# katha_long.yml's crons: Sunday Hindi, Wednesday Telugu (Python weekday: Mon=0 ... Sun=6).
LONG_DAYS = {6: "hi", 2: "te"}
# One-off runs outside that schedule, dispatched by hand: (date, lang). 2026-10-30 Telugu replaces the 10-28
# slot GitHub never fired; the 10-29 manual Gemini-written retry ran out of quota after 6 chapters.
EXTRA = [("2026-10-30", "te")]
CHAPTERS = 7
SCALE = 1.8                                  # write.write(chapter=True) scales the Short word range by this
FRAME_KEYS = ["title", "intro", "outro", "thumb_text", "kicker", "chapter_word", "intro_label", "outro_label",
              "subscribe", "description", "hashtags"]
SCRIPT_KEYS = ["title", "hook_text", "kicker", "sentences", "visuals", "claims_en"]


def words(lang):
    w0, w1 = LANGS[lang].get("words", (85, 110))
    return int(w0 * SCALE), int(w1 * SCALE)


def due(days=3):
    today = dt.datetime.now(dt.timezone.utc).date()
    out = []
    for i in range(days + 1):
        d = today + dt.timedelta(days=i)
        lang = LONG_DAYS.get(d.weekday()) or dict(EXTRA).get(str(d))
        if not lang or (DIR / f"{lang}_{d}.json").exists():
            continue
        cid = pick_collection(lang)
        used = {k for r in ledger() if r["lang"] == lang for k in r["keys"]}
        pool = [s for s in COLLECTIONS[cid]["pool"](lang) if s["key"] not in used] or COLLECTIONS[cid]["pool"](lang)
        L = LANGS[lang]
        out.append(dict(date=str(d), lang=lang, lang_name=L["name"], audience=L["audience"], collection=cid,
                        theme=COLLECTIONS[cid]["theme"], chapters=CHAPTERS, words=list(words(lang)), sentences="12-16",
                        candidates=[dict(key=s["key"], kind=s["kind"], wiki=s["wiki"], angle=s.get("angle", ""))
                                    for s in pool[:CHAPTERS + 4]],
                        file=f"katha/prewritten_long/{lang}_{d}.json", frame_prompt=FRAME))
    return out


def validate():
    bad = 0
    keys = {s["key"] for s in bank.S}
    for p in sorted(DIR.glob("*.json")):
        probs = []
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            lang = d["lang"]; w0, w1 = words(lang)
            if p.stem != f"{lang}_{d['date']}":
                probs.append("file name must be <lang>_<date>.json")
            if d.get("collection") not in COLLECTIONS:
                probs.append(f"unknown collection {d.get('collection')}")
            if not 3 <= len(d["chapters"]) <= CHAPTERS:
                probs.append(f"{len(d['chapters'])} chapters, need 3-{CHAPTERS}")
            for i, c in enumerate(d["chapters"], 1):
                s = c["script"]
                miss = [k for k in SCRIPT_KEYS if k not in s]
                n = len(" ".join(s.get("sentences", [])).split())
                probs += ([f"ch{i}: missing {miss}"] if miss else []) \
                    + ([f"ch{i}: {n} words, need {w0}-{w1}"] if not w0 <= n <= w1 else []) \
                    + ([f"ch{i}: {len(s.get('sentences', []))} sentences, need 12-16"] if not 12 <= len(s.get("sentences", [])) <= 16 else []) \
                    + ([f"ch{i}: key {c.get('key')} not in bank.py"] if c.get("key") not in keys else [])
            miss = [k for k in FRAME_KEYS if k not in d.get("frame", {})]
            if miss:
                probs.append(f"frame missing {miss}")
        except Exception as ex:
            probs.append(f"unreadable: {ex}")
        print(("OK  " if not probs else "BAD ") + p.name, probs)
        bad += bool(probs)
    return 1 if bad else 0


if __name__ == "__main__":
    if "validate" in sys.argv:
        sys.exit(validate())
    print(json.dumps(due(), ensure_ascii=False, indent=1 if "--json" not in sys.argv else None))
