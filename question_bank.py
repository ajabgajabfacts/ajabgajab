"""
question_bank.py — generate quiz questions at volume without shipping wrong answers.

The channel's rule has always been that facts are deterministic and the LLM is
never trusted with them. Going one-question-per-video breaks that rule's
economics: the hand-authored bank lasts about 40 days. So the LLM gets to write
questions, but it does not get to certify them.

The certification is the whole point of this file:

  * Blind cross-check. A DIFFERENT model answers the question cold — it never
    sees the proposed answer, and the options are shuffled so answer position
    leaks nothing. A model reviewing its own answer will confirm its own
    mistake; a model answering independently will not. Disagreement = discard.
  * Stability. A fact that expires is a wrong answer on a delay ("most NBA
    titles" is true until it isn't). Volatile answers are discarded.
  * Single defensible answer. Two-plausible-answers questions get argued with
    in the comments, and comments are the engagement signal we care about.
  * Dedup against the bank we already have.

Nothing here writes to the live rotation. Questions land in question_bank.json
as "pending" and only a human promotes them to "approved".

Usage:
    python question_bank.py generate --n 30 --concept geography --geo us
    python question_bank.py status
    python question_bank.py approve --all          # promote pending -> approved
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import random
import re
import sys
import time
from pathlib import Path

BANK = Path(__file__).parent / "question_bank.json"

# Gemini 503s under load, so a single hard-coded model means a dead run. Try them
# in order — but the verifier must NEVER be the model that wrote the question, or
# the cross-check degrades into a model marking its own homework, which is the one
# thing this file exists to prevent. So we track which model generated, and bar it
# from verifying.
MODEL_CHAIN = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
]


# ── Gemini ────────────────────────────────────────────────────────────────────
def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        f = Path(__file__).parent / "gemini_api.txt"
        if f.exists():
            k = f.read_text(encoding="utf-8").strip()
    if not k:
        raise SystemExit("No Gemini key: set GEMINI_API_KEY or create gemini_api.txt")
    return k


def _ask(model: str, prompt: str, temperature: float, max_tokens: int = 2000) -> str:
    from google import genai
    client = genai.Client(api_key=_key())
    cfg = {"temperature": temperature, "max_output_tokens": max_tokens,
           "response_mime_type": "application/json"}
    resp = client.models.generate_content(
        model=model, contents=prompt,
        config=genai.types.GenerateContentConfig(**cfg),
    )
    raw = (resp.text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw


def ask_any(prompt: str, temperature: float, max_tokens: int = 2000,
            exclude: str = "") -> tuple[str, str]:
    """Ask the first model in the chain that answers. Returns (text, model_used).

    `exclude` bars a model — used to keep the verifier honest by preventing it
    from being the same model that wrote the question.
    """
    last = None
    for model in MODEL_CHAIN:
        if model == exclude:
            continue
        for attempt in range(3):
            try:
                return _ask(model, prompt, temperature, max_tokens), model
            except Exception as e:
                last = e
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    # Free tier is 15 req/min/model and the server says how long
                    # to wait — waiting beats falling through the whole chain,
                    # which just spends the other models' quota on the same
                    # minute window.
                    m = re.search(r"retry in (\d+)", msg)
                    time.sleep(min(int(m.group(1)) + 2 if m else 50, 70))
                    continue
                if "503" in msg or "UNAVAILABLE" in msg:
                    time.sleep(2 + 3 * attempt)     # transient — worth a retry
                    continue
                break                                # a real error; try the next model
        print(f"[Gemini] {model} unavailable — falling back")
    raise SystemExit(f"All Gemini models failed. Last error: {last}")


# ── Bank I/O ──────────────────────────────────────────────────────────────────
def load_bank() -> list:
    if not BANK.exists():
        return []
    return json.loads(BANK.read_text(encoding="utf-8")).get("questions", [])


def save_bank(qs: list) -> None:
    BANK.write_text(json.dumps({"questions": qs}, indent=1, ensure_ascii=False),
                    encoding="utf-8")


def _norm(s: str) -> set:
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split() if len(w) > 2}


def is_duplicate(q: str, existing: list[str], thresh: float = 0.6) -> bool:
    """Token-overlap dedup. Catches rewordings of a question we already ask."""
    a = _norm(q)
    if not a:
        return True
    for e in existing:
        b = _norm(e)
        if b and len(a & b) / len(a | b) >= thresh:
            return True
    return False


def existing_questions() -> list[str]:
    """Everything already asked — the hand-authored quizzes plus the bank."""
    return [it["q"] for it in existing_items()]


def existing_items() -> list[dict]:
    """Every question already asked, WITH its fact and answer — the dedup
    corpus. Question text alone is not enough: the YPP repetitious-content
    risk is the same FACT re-asked in different words, which no wording
    comparison can catch."""
    out = []
    for r in load_bank():
        if r.get("status") == "rejected":
            continue
        out.append({"q": r["q"], "fact": r.get("fact", ""),
                    "ans": str(r["options"][r["answer"]]) if r.get("options") else ""})
    try:
        from charts import QUIZZES
        for quiz in QUIZZES:
            for q in quiz.get("questions", []):
                if q.get("q"):
                    ans = ""
                    if q.get("options") and isinstance(q.get("answer"), int) and q["answer"] >= 0:
                        ans = str(q["options"][q["answer"]])
                    out.append({"q": q["q"], "fact": q.get("fact", ""), "ans": ans})
    except Exception as e:
        print(f"[Bank] could not read existing quizzes: {e}")
    return out


# ── Semantic (same-fact) dedup ────────────────────────────────────────────────
SAME_FACT_PROMPT = """A quiz channel must never re-test a fact it has already used —
YouTube treats it as repetitious content. Below is one NEW question and a numbered
list of EXISTING questions.

NEW question: {q}
NEW answer: {ans}
NEW fact: {fact}

EXISTING:
{listing}

Does the NEW question test the same underlying fact as ANY existing one? Same fact
means a viewer who saw the existing video already knows this answer — different
wording, same knowledge. Merely sharing a broad subject (both about cricket, both
about the Moon) is NOT the same fact.

Return JSON only: {{"same_fact": <true|false>, "of": <number or null>, "why": "<short>"}}"""


def _fact_tokens(item: dict) -> set:
    return _norm(f"{item.get('fact', '')} {item.get('ans', '')}")


def same_fact_as_existing(cand: dict, corpus: list[dict],
                          exclude: str = "") -> tuple[bool, str]:
    """Fact-level dedup in two layers. Layer 1 is free: heavy token overlap on
    fact+answer means the same fact regardless of question wording. Layer 2
    shortlists mild overlaps and asks a model whether any tests the same
    knowledge — one call per candidate, and only when the shortlist is
    non-empty. Fails OPEN on model errors: dedup is a quality gate, not a
    correctness gate, and a false 'duplicate' throws away verified work."""
    c = {"fact": cand.get("fact", ""),
         "ans": str(cand["options"][cand["answer"]])}
    a = _fact_tokens(c)
    if not a:
        return False, ""
    shortlist = []
    for e in corpus:
        b = _fact_tokens(e)
        if not b:
            continue
        j = len(a & b) / len(a | b)
        if j >= 0.5:
            return True, f"fact tokens match existing: {e['q'][:60]}"
        if j >= 0.18:
            shortlist.append((j, e))
    if not shortlist:
        return False, ""
    shortlist = [e for _, e in sorted(shortlist, key=lambda t: -t[0])[:8]]
    listing = "\n".join(f"{i + 1}) {e['q']} -> {e['ans']}"
                        for i, e in enumerate(shortlist))
    try:
        raw, _m = ask_any(
            SAME_FACT_PROMPT.format(q=cand["q"], ans=c["ans"],
                                    fact=c["fact"], listing=listing),
            temperature=0.0, max_tokens=300, exclude=exclude)
        v = json.loads(raw)
    except (SystemExit, json.JSONDecodeError):
        return False, ""    # fail open — see docstring
    if v.get("same_fact"):
        of = v.get("of")
        which = shortlist[of - 1]["q"][:60] if isinstance(of, int) and 1 <= of <= len(shortlist) else "?"
        return True, f"same fact as: {which} ({(v.get('why') or '')[:80]})"
    return False, ""


# ── Generation ────────────────────────────────────────────────────────────────
GEN_PROMPT = """Write {n} multiple-choice quiz questions for a YouTube Shorts trivia channel.

Topic area: {concept}
Audience: {audience}

Hard requirements — a question that breaks any of these is useless to us:
- The answer must be a settled, verifiable fact that will STILL be correct in 10
  years. No records that get broken, no "current" holders, no populations, no
  rankings that shift year to year, nothing dated after 2020.
- EXACTLY ONE option may be defensibly correct. The other two must be clearly,
  checkably wrong — not "arguably also right".
- The question must be instantly understandable when read aloud in 3 seconds.
- Surprising beats obscure. The best question makes a viewer say "wait, really?"
  and then argue about it in the comments. Avoid textbook trivia nobody disputes.
- 3 options each, all plausible to someone who does not know the answer.

Return JSON only:
{{"questions": [
  {{"q": "the question", "options": ["a","b","c"], "answer": 0,
    "fact": "one sentence stating the answer and why it is true",
    "emoji": "a single emoji representing the question's subject",
    "image_query": "1-3 English words for a stock-photo background"}}
]}}
"answer" is the 0-based index into options.
"emoji" must be exactly one emoji character and should depict the SUBJECT of the
question (a question about the Moon -> a moon; about baseball -> a baseball). It
becomes the artwork on the question card and the marker that rolls down the
countdown bar, so pick something recognisable at a glance.
"image_query" is one to three ENGLISH words naming a photographable, spoiler-free
subject for the background photo — the question's setting or theme, and NEVER the
answer or any option (a photo of the answer gives the quiz away). Taj Mahal question
-> "taj mahal"; cricket question -> "cricket stadium"; body question -> "human anatomy".
English only, because the stock-photo library is searched in English.

Do not repeat any of these existing questions:
{avoid}
"""

VERIFY_PROMPT = """Answer this multiple-choice question. You are the sole fact-checker.

Question: {q}
Options:
0) {o0}
1) {o1}
2) {o2}

Return JSON only:
{{"answer": <0,1,2>,
  "confident": <true|false>,
  "single_defensible_answer": <true|false>,
  "stable_for_10_years": <true|false>,
  "note": "<brief reason if anything is wrong with the question>"}}

"single_defensible_answer" is false if more than one option could reasonably be
argued correct. "stable_for_10_years" is false if the correct answer could change
over time (a record, a ranking, a current holder, a population figure).
"""


def _salvage_items(raw: str) -> list:
    """Recover the complete question objects from a truncated JSON response.

    gemini-flash-latest spends a variable, sometimes large slice of its output
    budget on hidden 'thinking' tokens, so the JSON array is intermittently cut
    off mid-object — which used to yield "0 well-formed candidates" and waste the
    whole call. The items are flat (no nested braces; lists use brackets), so every
    complete `{...}` can be lifted out individually and the truncated tail dropped.
    """
    out = []
    for m in re.findall(r"\{[^{}]*\}", raw):
        try:
            out.append(json.loads(m))
        except json.JSONDecodeError:
            pass
    return out


def generate(n: int, concept: str, geo: str) -> tuple[list, str]:
    if geo == "india":
        audience = (
            "India — Hinglish-speaking viewers including Tier-2/3 cities and rural areas. "
            "Facts should be about India, OR globally amazing facts an Indian audience loves: "
            "Bollywood and South-Indian film trivia, cricket history, Indian history and "
            "geography, science, world records, mythology. Mass-appeal and surprising over "
            "obscure. For film/celebrity facts use verifiable trivia (year, who did what, "
            "records set), never opinion. Write the question and fact in clear ENGLISH — it is "
            "localised to Hinglish later.")
    elif geo == "us":
        audience = ("United States — the questions should be about the US, or framed "
                    "for an American viewer")
    else:
        audience = "global"
    avoid = "\n".join("- " + q for q in existing_questions()[-80:]) or "- (none yet)"
    raw, model = ask_any(
        GEN_PROMPT.format(n=n, concept=concept, audience=audience, avoid=avoid),
        temperature=1.0, max_tokens=500 * n + 2000)   # headroom or the JSON truncates
    try:
        items = json.loads(raw).get("questions", [])
    except json.JSONDecodeError:
        items = _salvage_items(raw)     # truncated tail — keep the complete items
        if items:
            print(f"[Gen] JSON truncated — salvaged {len(items)} complete items")
        else:
            print(f"[Gen] bad JSON from {model} and nothing salvageable")
            return [], model
    out = []
    for it in items:
        opts = it.get("options") or []
        if not it.get("q") or len(opts) != 3:
            continue
        if not isinstance(it.get("answer"), int) or not 0 <= it["answer"] <= 2:
            continue
        out.append({"q": it["q"].strip(), "options": [str(o).strip() for o in opts],
                    "answer": it["answer"], "fact": (it.get("fact") or "").strip(),
                    "emoji": (it.get("emoji") or "").strip()[:4],
                    "image_query": (it.get("image_query") or "").strip()[:60],
                    "concept": concept, "geo": geo})
    return out, model


# ── Verification ──────────────────────────────────────────────────────────────
FACT_PROMPT = """A quiz question, the answer it claims is correct, and the explanation
it gives. Judge ONLY whether the explanation actually supports that answer.

Question: {q}
Claimed correct answer: {ans}
Explanation given: {fact}

Return JSON only:
{{"supports": <true|false>, "why": "<one short sentence>"}}

"supports" is false if the explanation contradicts the claimed answer, argues for a
different option, denies the premise of the question, or describes something that is
not the answer at all. Example of false: the answer is "BMW" to "which logo was
originally a propeller?" and the explanation says the logo "represents the Bavarian
flag, NOT a propeller" — the explanation refutes the answer.
"""


def fact_supports_answer(item: dict, exclude: str = "") -> tuple[bool, str]:
    """Does the question's own `fact` actually back its answer?

    The blind verifier CANNOT catch this — it never sees the fact, by design. So a
    question sailed through where the answer was "BMW" and the fact read "the BMW
    logo represents the Bavarian flag, NOT a spinning airplane propeller". The
    explanation refuted the answer it was attached to, and the fact is the line the
    narrator reads aloud on the reveal.

    A cheap guard first: if the fact denies the answer outright, or names a
    different option as the true one, no model call is needed.
    """
    ans   = str(item["options"][item["answer"]])
    fact  = item.get("fact") or ""
    lo    = fact.lower()

    if not fact.strip():
        return False, "no fact given"

    # "... is NOT a propeller", "not Maine", "rather than X"
    if re.search(r"\bnot\b[^.]{0,40}" + re.escape(ans.lower()[:20]), lo):
        return False, f"the fact denies the answer ({ans})"

    # the fact champions one of the WRONG options instead
    for i, opt in enumerate(item["options"]):
        if i == item["answer"]:
            continue
        o = str(opt).lower()
        if len(o) > 3 and re.search(r"\b" + re.escape(o) + r"\b[^.]{0,30}\b(is|was|holds|remains|actually)\b", lo):
            return False, f"the fact argues for a different option ({opt})"

    raw, _m = ask_any(FACT_PROMPT.format(q=item["q"], ans=ans, fact=fact),
                      temperature=0.0, max_tokens=300, exclude=exclude)
    try:
        v = json.loads(raw)
    except json.JSONDecodeError:
        return True, "fact check unparseable — allowed"     # never block on a parse error
    if not v.get("supports", True):
        return False, f"fact does not support the answer: {(v.get('why') or '')[:90]}"
    return True, ""


def verify(item: dict, wrote_it: str = "") -> tuple[bool, dict]:
    """Blind cross-check by a DIFFERENT model. The verifier never sees the
    proposed answer, the options are shuffled so position carries no signal, and
    the model that wrote the question is barred from grading it. Returns
    (passed, checks)."""
    order = list(range(3))
    random.shuffle(order)
    shown = [item["options"][i] for i in order]          # shuffled options
    truth_pos = order.index(item["answer"])              # where the truth now sits

    raw, ver_model = ask_any(
        VERIFY_PROMPT.format(q=item["q"], o0=shown[0], o1=shown[1], o2=shown[2]),
        temperature=0.0, exclude=wrote_it)
    try:
        v = json.loads(raw)
    except json.JSONDecodeError:
        return False, {"reason": "verifier returned unparseable JSON"}

    checks = {
        "verifier_agreed":  v.get("answer") == truth_pos,
        "confident":        bool(v.get("confident")),
        "single_answer":    bool(v.get("single_defensible_answer")),
        "stable":           bool(v.get("stable_for_10_years")),
        "note":             (v.get("note") or "")[:200],
        "verified_by":      ver_model,
    }
    passed = all([checks["verifier_agreed"], checks["confident"],
                  checks["single_answer"], checks["stable"]])
    if not checks["verifier_agreed"]:
        checks["reason"] = "verifier disagreed with the proposed answer"
    elif not checks["stable"]:
        checks["reason"] = "answer could change over time"
    elif not checks["single_answer"]:
        checks["reason"] = "more than one defensible answer"
    elif not checks["confident"]:
        checks["reason"] = "verifier not confident"
    return passed, checks


# ── Commands ──────────────────────────────────────────────────────────────────
def cmd_generate(args) -> None:
    bank    = load_bank()
    corpus  = existing_items()
    already = [it["q"] for it in corpus]
    print(f"[Bank] {len(bank)} in bank, {len(already)} questions already asked")
    print(f"[Gen] writing {args.n} × {args.concept} ({args.geo}) ...")

    cands, wrote_it = generate(args.n, args.concept, args.geo)
    print(f"[Gen] {len(cands)} well-formed candidates from {wrote_it}")
    print(f"[Gen] verifying blind with a different model (never {wrote_it})\n")

    kept = dropped = 0
    for c in cands:
        if is_duplicate(c["q"], already):
            print(f"  [dup ] {c['q'][:62]}")
            dropped += 1
            continue
        try:
            # Same-fact check runs BEFORE the blind verify on purpose: a
            # duplicate costs one model call here instead of three there.
            same, which = same_fact_as_existing(c, corpus, exclude=wrote_it)
            if same:
                print(f"  [sema] {c['q'][:62]}\n         -> {which}")
                dropped += 1
                continue
            ok, checks = verify(c, wrote_it=wrote_it)
            if not ok:
                print(f"  [FAIL] {c['q'][:62]}\n         -> {checks.get('reason','?')}")
                dropped += 1
                continue

            # The reveal reads the fact aloud, so a fact that refutes its own answer
            # ships a self-contradicting video. The blind verifier cannot see this.
            fact_ok, why = fact_supports_answer(c, exclude=wrote_it)
        except SystemExit as e:
            # Quota exhausted mid-batch. Everything verified so far is already
            # saved (see below) — losing the tail is fine, losing the batch is
            # not (a 429 at candidate 8 of 15 used to discard 7 good questions).
            print(f"\n[Gen] stopping early — {e}")
            break
        if not fact_ok:
            print(f"  [FACT] {c['q'][:62]}\n         -> {why}")
            checks["fact_conflict"] = why
            dropped += 1
            continue
        c.update(status="pending", checks=checks,
                 created=datetime.date.today().isoformat())
        bank.append(c)
        already.append(c["q"])
        corpus.append({"q": c["q"], "fact": c.get("fact", ""),
                       "ans": str(c["options"][c["answer"]])})
        kept += 1
        save_bank(bank)     # incremental — a crash must never cost verified work
        print(f"  [ok  ] {c['q'][:62]}\n         -> {c['options'][c['answer']]}")

    save_bank(bank)
    print(f"\n[Bank] kept {kept}, dropped {dropped} "
          f"({dropped / max(len(cands), 1):.0%} rejected) -> {BANK.name}")
    print("[Bank] new questions are PENDING — review, then: python question_bank.py approve --all")


def cmd_status(args) -> None:
    bank = load_bank()
    by = {}
    for q in bank:
        by[q.get("status", "?")] = by.get(q.get("status", "?"), 0) + 1
    print(f"{len(bank)} questions in bank: {by or '(empty)'}")
    for q in bank:
        if q.get("status") == "pending":
            print(f"  [pending] {q['q']}\n            -> {q['options'][q['answer']]}")


def cmd_approve(args) -> None:
    bank = load_bank()
    n = 0
    for q in bank:
        if q.get("status") == "pending":
            q["status"] = "approved"
            n += 1
    save_bank(bank)
    print(f"[Bank] approved {n} question(s)")


def cmd_reject(args) -> None:
    """Drop a question by its 1-based position in `status`.

    A question can be perfectly TRUE and still be a bad quiz question — the one
    this was written for ("how many US states lie north of Canada's southernmost
    point?") is factually correct, and hinges on a 9km margin no viewer could
    reason about or check. Truth is the verifier's job; being worth asking is yours.
    """
    bank = load_bank()
    idx  = args.n - 1
    if not 0 <= idx < len(bank):
        raise SystemExit(f"No question #{args.n} (bank has {len(bank)})")
    bank[idx]["status"] = "rejected"
    bank[idx]["rejected_reason"] = args.reason or "not worth asking"
    save_bank(bank)
    print(f"[Bank] rejected #{args.n}: {bank[idx]['q'][:60]}")
    print(f"       reason: {bank[idx]['rejected_reason']}")


def main() -> None:
    p   = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate + verify a batch")
    g.add_argument("--n", type=int, default=20)
    g.add_argument("--concept", default="geography")
    g.add_argument("--geo", default="global", choices=["global", "us", "india"])
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("status", help="show the bank")
    s.set_defaults(func=cmd_status)

    a = sub.add_parser("approve", help="promote pending -> approved")
    a.add_argument("--all", action="store_true")
    a.set_defaults(func=cmd_approve)

    j = sub.add_parser("reject", help="drop a question by its number in `status`")
    j.add_argument("n", type=int)
    j.add_argument("--reason", default="")
    j.set_defaults(func=cmd_reject)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
