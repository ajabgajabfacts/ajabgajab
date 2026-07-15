"""
audit_narration.py — read what the channel actually SAYS, and grade it.

The narration is the one part of a video nobody ever looks at: it is generated
deterministically from the question data, spoken by a TTS voice, and shipped. It
is also the first thing a viewer hears, and the thing that decides whether they
stay past the hook.

This prints the narration for every quiz, scores the hook, times it against the
real speech clock, and flags the things that only bite once a voice reads them
aloud (a "$1M" that gets read as "dollar one em", a hook buried 12 seconds in).

    python audit_narration.py                 # score every quiz, worst hooks first
    python audit_narration.py --full          # print the full narration of each
    python audit_narration.py --key odds_quiz # one quiz, in detail
    python audit_narration.py --llm           # add a Gemini critique of each hook

Nothing here changes a video. It is a mirror.
"""

from __future__ import annotations

import argparse
import re
import sys

from charts import QUIZZES, build_segments, _narration
from quality_scorer import score_viral_hook

# Calibrated against real renders, not a textbook speaking rate: penny_doubling
# is 123 words and runs 68.9s, odds_quiz is 112 words and runs 56.5s. The gap is
# the "Three... two... one..." countdowns, whose pauses cost far more time than
# their word count suggests — the same fact that made word-share captioning drift
# seconds out of sync. A naive 2.6 w/s underestimated penny_doubling by 22s.
WORDS_PER_SEC = 1.85


# Do NOT add "TTS traps" here from intuition. I did, and every one was wrong.
#
# I assumed edge-tts would mangle bare years, "$5M", "&", "vs" and "3/3", so I
# flagged them all. Then I measured it — synthesising each form against its
# written-out equivalent and comparing audio length, on the theory that a voice
# spelling out digits takes measurably longer:
#
#   "landed in 1969"        3.46s vs "nineteen sixty-nine"        3.43s
#   "$5M right now"         2.66s vs "Five million dollars..."    2.71s
#   "$10k a month"          2.42s vs "Ten thousand dollars..."    2.42s
#   "Alaska & Hawaii"       2.23s vs "Alaska and Hawaii"          2.18s
#   "Britain vs Zanzibar"   2.35s vs "Britain versus Zanzibar"    2.35s
#   "You got 3/3"           2.38s vs "three out of three"         2.38s
#
# Identical, every time. edge-tts normalises all of it correctly. The rules were
# pure noise, and acting on them would have meant rewriting narration that was
# never broken. If you suspect a new trap, MEASURE IT the same way before adding
# it here. (Markdown is genuinely read aloud — but generate_voiceover already
# strips it before synthesis, so it never reaches the voice.)
TTS_TRAPS: list = []


def audit(quiz: dict, full: bool = False) -> dict:
    segs  = build_segments(quiz)
    narr  = _narration(quiz)
    hook  = quiz["hook"]
    words = len(narr.split())

    score, hits = score_viral_hook(hook)

    # When does the viewer actually hear question 1? Everything before it is a
    # tax they pay to reach the content.
    intro_words = len(segs[0][2].split())
    time_to_q1  = intro_words / WORDS_PER_SEC

    traps = []
    for pattern, msg in TTS_TRAPS:
        for m in re.finditer(pattern, narr):
            traps.append(f"{msg}  [{m.group(0)!r}]")

    return {
        "key": quiz["key"], "format": quiz["format"], "hook": hook,
        "hook_score": score, "hook_hits": hits,
        "words": words, "est_seconds": words / WORDS_PER_SEC,
        "time_to_q1": time_to_q1,
        "traps": sorted(set(traps)),
        "narration": narr if full else "",
    }


def llm_critique(rows: list) -> dict:
    """Ask Gemini to critique the weakest hooks. Opinion, not gospel — it never
    edits anything, it just tells you where it would."""
    try:
        from question_bank import _ask
    except Exception as e:
        print(f"[LLM] unavailable: {e}")
        return {}
    worst = sorted(rows, key=lambda r: r["hook_score"])[:8]
    listing = "\n".join(f'{r["key"]}: "{r["hook"]}"' for r in worst)
    prompt = (
        "These are the opening spoken lines of quiz YouTube Shorts. The viewer "
        "hears this first and decides within about a second whether to swipe.\n\n"
        f"{listing}\n\n"
        "For each, say in one short sentence what is weak about it, then give ONE "
        "rewritten hook of 6-14 words that creates a stronger curiosity gap. Do not "
        "invent facts — the rewrite must promise only what a 3-question general "
        "knowledge quiz can deliver.\n"
        'Return JSON: {"critiques":[{"key":"...","weakness":"...","rewrite":"..."}]}'
    )
    import json as _json
    try:
        return {c["key"]: c for c in _json.loads(_ask("gemini-flash-latest", prompt, 0.7, 3000))["critiques"]}
    except Exception as e:
        print(f"[LLM] critique failed: {e}")
        return {}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key",  help="audit a single quiz")
    ap.add_argument("--full", action="store_true", help="print the full narration")
    ap.add_argument("--llm",  action="store_true", help="add a Gemini critique of the weakest hooks")
    a = ap.parse_args()

    quizzes = [q for q in QUIZZES if not a.key or q["key"] == a.key]
    if not quizzes:
        raise SystemExit(f"No quiz with key {a.key!r}")

    rows = [audit(q, full=a.full or bool(a.key)) for q in quizzes]
    rows.sort(key=lambda r: r["hook_score"])

    crit = llm_critique(rows) if a.llm else {}

    print(f"\n{len(rows)} quizzes — weakest hooks first "
          f"(hook is now the ENTIRE intro, so it is the first thing heard)\n")
    print(f"{'key':22}{'fmt':8}{'hook':>5}{'words':>7}{'est':>7}{'->Q1':>7}  issues")
    print("-" * 96)
    for r in rows:
        flags = []
        if r["time_to_q1"] > 4.0:
            flags.append(f"{r['time_to_q1']:.1f}s before question 1")
        if r["est_seconds"] > 55:
            flags.append(f"~{r['est_seconds']:.0f}s narration (long)")
        if r["traps"]:
            flags.append(f"{len(r['traps'])} TTS trap(s)")
        print(f"{r['key']:22}{r['format']:8}{r['hook_score']:5.1f}{r['words']:7}"
              f"{r['est_seconds']:6.0f}s{r['time_to_q1']:6.1f}s  {'; '.join(flags)}")

    for r in rows:
        if not (a.key or a.full or r["traps"] or r["hook_score"] < 4):
            continue
        print(f"\n=== {r['key']} ({r['format']}) — hook {r['hook_score']:.1f}/10")
        print(f'  hook: "{r["hook"]}"')
        print(f"  hits: {', '.join(r['hook_hits'])}")
        for t in r["traps"]:
            print(f"  TTS:  {t}")
        if r["key"] in crit:
            c = crit[r["key"]]
            print(f"  LLM weakness: {c['weakness']}")
            print(f"  LLM rewrite : \"{c['rewrite']}\"")
        if r["narration"]:
            print("  --- spoken ---")
            for line in re.split(r"(?<=[.!?])\s+", r["narration"]):
                if line.strip():
                    print(f"    {line.strip()}")

    print(f"\nmean hook score: {sum(r['hook_score'] for r in rows)/len(rows):.1f}/10")
    print("Nothing was changed. Rewrite hooks in charts.py QUIZZES to act on this.")


if __name__ == "__main__":
    main()
