"""Scripts written ahead of their slot: by the daily Claude routine, then gaps filled by Gemini.

Owner, 2026-10-27: Claude writes the main scripts (a daily claude.ai routine, ~19:30 UTC, using
`--plan --json` to see what is needed and backup.py to fetch sources), and Gemini double-checks
each one with write.py's CHECK prompt (one call each) - an independent model, as before.

  ~19:30 UTC  Claude routine writes katha/prewritten/<lang>_<key>.json with "verified": false
  21:30 UTC   prewrite.yml --verify-only: Gemini CHECK; pass -> verified, fail -> deleted
  03:15 UTC   prewrite.yml: verify anything left, then write the remaining gaps with Gemini, using
              the quota the day left before its ~07:00 UTC reset

make.py posts verified scripts first and only falls back to an unverified one on a day Gemini is down.

    python katha/prewrite.py                 # verify, then fill the gaps with Gemini
    python katha/prewrite.py --verify-only
    python katha/prewrite.py --plan [--json] # what is still needed (the routine reads --json)
"""
import argparse, datetime as dt, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ai, make, media, write
from langs import LANGS

DIR = make.PREWRITTEN
MAX_WRITES = 8                       # a script costs 2-8 text calls (writer + checker, up to 4 rounds)
EN_SLOT = 4                          # Wait, That's Real? (katha_en.yml), evening
EN_SLOT2 = 5                         # its midday Short from 2026-10-31; not Sun/Wed (Ajab long-form quota days)


def en_slots(day):
    return (EN_SLOT,) if day.weekday() in (2, 6) else (EN_SLOT, EN_SLOT2)


def upcoming():
    """(day, slot, lang) still to post today and all of tomorrow, soonest first."""
    today = dt.date.today()
    posted = {(r.get("date"), r.get("slot")) for r in make.ledger() if r.get("status") == "posted"}
    out = []
    for day in (today, today + dt.timedelta(days=1)):
        extra = (make.festivals.EXTRA_SLOT,) if make.festivals.extra_slot_on(day, make._done_before(day)) else ()
        for slot in (0, 1, 2, 3) + extra:
            if (str(day), slot) not in posted:
                out.append((day, slot, make.slot_lang(slot, day)))
        for slot in en_slots(day):
            if (str(day), slot) not in posted:
                out.append((day, slot, "en"))
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


def plan():
    """The slots no prewritten script covers yet, each with the story make.py would pick for it."""
    have = stock()
    left = {l: len(k) for l, k in have.items()}
    taken = {l: list(k) for l, k in have.items()}
    out = []
    for day, slot, lang in upcoming():
        # A festival story for this day is written ahead even when other stock exists (festivals.py):
        # make.pick posts it first, so stock would not cover it.
        fest = make.pick(lang, exclude=taken.get(lang, []), day=day, slot=slot)
        if lang != "en" and fest["key"] in make.festivals.keys_for(lang, day):
            if fest["key"] in have.get(lang, []):
                continue                                      # already written
            e = fest
        elif left.get(lang, 0) > 0:
            left[lang] -= 1                                   # this slot is covered
            continue
        else:
            e = make.pick(lang, exclude=taken.get(lang, []), day=day, slot=slot)
        taken.setdefault(lang, []).append(e["key"])
        ch = make.insights.load().get("channels", {}).get("en" if lang == "en" else "ajab", {}) or {}
        out.append(dict(day=str(day), slot=slot, lang=lang,
                        entry=dict(e, proven=(ch.get("proven_titles") or {}).get(lang, []))))
    return out


def source_text(e):
    sources = media.wiki(e["wiki"])
    return "\n\n".join(f"### {s['title']}\n{s['text']}" for s in sources) if sources else ""


def verify():
    """Gemini CHECK on every script the Claude routine wrote (prewritten and backup). False if Gemini is down."""
    for p in sorted(DIR.glob("*.json")) + sorted(make.BACKUP.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("verified", True):
            continue
        lang, key = p.stem.split("_", 1)
        e = next((x for x in make.bank.S if x["key"] == key), None)
        src = source_text(e) if e else ""
        if not src:
            p.unlink(); print(f"[verify] {p.name}: no bank entry / source, removed"); continue
        L = LANGS[lang]; s = d["script"]
        w0, w1 = L.get("words", (85, 110))
        try:
            c = ai.json_call(write.CHECK.format(
                lang_name=L["name"], w0=w0, w1=w1, source=src[:14000], script="\n".join(s["sentences"]),
                claims="\n".join("- " + x for x in s.get("claims_en", [])), **write.SHORT),
                models=ai.CHECK_MODELS, temperature=0.1)
        except Exception as err:
            print(f"[verify] stopping, Gemini unavailable: {str(err)[:120]}"); return False
        if c.get("ok"):
            d.update(verified=True, gemini_check=c)
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[verify] {p.name}: passed")
        else:
            # Deleted, not retired: the 03:15 run (or tomorrow's routine) writes the story afresh.
            p.unlink(); print(f"[verify] {p.name}: REJECTED, removed: {c.get('problems', [])[:3]}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--json", action="store_true", help="with --plan: machine-readable, for the routine")
    ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args()
    DIR.mkdir(exist_ok=True)
    if a.plan:
        todo = plan()
        if a.json:
            print(json.dumps([dict(t, words=list(LANGS[t["lang"]].get("words", (85, 110))),
                                   lang_name=LANGS[t["lang"]]["name"], audience=LANGS[t["lang"]].get("audience"))
                              for t in todo], ensure_ascii=False, indent=1))
        else:
            print(f"[prewrite] in stock: { {l: len(k) for l, k in stock().items()} }  "
                  f"to write: {[(t['day'], t['slot'], t['lang'], t['entry']['key']) for t in todo]}")
        return
    if not verify() or a.verify_only:
        return

    written = 0
    for t in plan():
        if written >= MAX_WRITES:
            break
        lang, e = t["lang"], t["entry"]
        src = source_text(e)
        if not src:
            print(f"[prewrite] {lang}/{e['key']}: no source text, skipped"); continue
        try:
            s, chk = write.write(e, lang, LANGS[lang], src)
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
            script=s, check=chk, verified=True, by="gemini",
            written=dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
            for_slot=f"{t['day']} slot {t['slot']}"), ensure_ascii=False, indent=1), encoding="utf-8")
        written += 1
        print(f"[prewrite] wrote {lang}/{e['key']} (for {t['day']} slot {t['slot']}): {s['title']}")
    print(f"[prewrite] {written} written")


if __name__ == "__main__":
    main()
