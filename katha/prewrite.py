"""Write the next story scripts tonight, with the Gemini quota the day left unused.

The free tier resets about 07:00 UTC, and most days the posts leave text quota spare. This
runs shortly before the reset and writes + fact-checks scripts for the rest of today's and
all of tomorrow's slots, into katha/prewritten/<lang>_<key>.json. make.py picks those
stories first and skips its own writer, so a post on a day whose quota runs out (2026-10-25:
every run from 16:42 failed) still goes up: it only needs the vision and TTS models, which
have their own quotas, and edge-tts covers TTS too.

Same writer, same checker (write.py) - nothing about the script changes, only when it is written.

    python katha/prewrite.py           # fill the stock for the next slots
    python katha/prewrite.py --plan    # show what it would write, write nothing
"""
import argparse, datetime as dt, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make, media, write
from langs import LANGS

DIR = make.PREWRITTEN
MAX_WRITES = 8                       # a script costs 2-8 text calls (writer + checker, up to 4 rounds)
EN_SLOT = 4                          # Strange But True (katha_en.yml)


def upcoming():
    """(day, slot, lang) still to post today and all of tomorrow, soonest first."""
    today = dt.date.today()
    led = make.ledger()
    posted = {(r.get("date"), r.get("slot")) for r in led if r.get("status") == "posted"}
    out = []
    for day in (today, today + dt.timedelta(days=1)):
        for slot in (0, 1, 2, 3):
            if (str(day), slot) not in posted:
                out.append((day, slot, make.slot_lang(slot, day)))
        if (str(day), EN_SLOT) not in posted:
            out.append((day, EN_SLOT, "en"))
    return out


def stock():
    """{lang: [key, ...]} written and not yet posted or retired; stale files are removed."""
    done = {(r["key"], r["lang"]) for r in make.ledger() if r.get("status") in ("posted", "failed_check")}
    have = {}
    for p in sorted(DIR.glob("*.json")):
        lang, key = p.stem.split("_", 1)
        if (key, lang) in done:
            p.unlink(); print(f"[prewrite] removed {p.name} (already posted or retired)")
        else:
            have.setdefault(lang, []).append(key)
    return have


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    a = ap.parse_args()
    DIR.mkdir(exist_ok=True)
    have = stock()
    left = {l: len(k) for l, k in have.items()}
    todo = []
    for day, slot, lang in upcoming():
        if left.get(lang, 0) > 0:
            left[lang] -= 1                                   # this slot is covered
        else:
            todo.append((day, slot, lang))
    print(f"[prewrite] in stock: { {l: len(k) for l, k in have.items()} }  to write: {[(str(d), s, l) for d, s, l in todo]}")
    if a.plan:
        return

    written = 0
    for day, slot, lang in todo:
        if written >= MAX_WRITES:
            break
        L = LANGS[lang]
        e = make.pick(lang, exclude=have.get(lang, []))
        ch = make.insights.load().get("channels", {}).get("en" if lang == "en" else "ajab", {}) or {}
        e = dict(e, proven=(ch.get("proven_titles") or {}).get(lang, []))
        sources = media.wiki(e["wiki"])
        if not sources:
            print(f"[prewrite] {lang}/{e['key']}: no source text, skipped"); continue
        src = "\n\n".join(f"### {s['title']}\n{s['text']}" for s in sources)
        try:
            s, chk = write.write(e, lang, L, src)
        except Exception as err:
            if str(err).startswith("no script passed"):
                # Retired the same way make.py retires it, so neither picks it again.
                led = make.ledger()
                led.append(dict(key=e["key"], lang=lang, date=str(dt.date.today()), status="failed_check",
                                why=str(err)[:200], by="prewrite"))
                make.LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"[prewrite] {lang}/{e['key']}: failed the check, retired"); continue
            print(f"[prewrite] stopping, Gemini unavailable: {str(err)[:120]}"); break
        (DIR / f"{lang}_{e['key']}.json").write_text(json.dumps(dict(
            script=s, check=chk, written=dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
            for_slot=f"{day} slot {slot}"), ensure_ascii=False, indent=1), encoding="utf-8")
        have.setdefault(lang, []).append(e["key"]); written += 1
        print(f"[prewrite] wrote {lang}/{e['key']} (for {day} slot {slot}): {s['title']}")
    print(f"[prewrite] {written} written")


if __name__ == "__main__":
    main()
