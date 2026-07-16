"""
backgrounds.py — real photo backgrounds from Pexels, picked to suit the question.

Quizora's dark matplotlib canvas reads as "generated". A photo behind the
question card reads as a real video, which is what the channels winning this
format do.

Two things this file is careful about:

  * Relevance. The search term is built from the ANSWER, not the question — a
    question about which country drinks the most beer wants a photo of Germany,
    and the answer is the only part of the quiz that names it.
  * Repetition. Reusing the same stock photo across videos is exactly the
    signature YouTube's repetitious-content review looks for, so recently used
    photo IDs are remembered and skipped.

No Pexels key -> returns None -> the renderer keeps the existing dark canvas.
Nothing breaks; the feature is simply dormant.
"""

from __future__ import annotations

import json
import os
import random
import re
import urllib.parse
import urllib.request
from pathlib import Path

USED    = Path(__file__).parent / "bg_used.json"
KEEP    = 60            # remember this many recent photos before allowing a repeat
W, H    = 1080, 1920
TIMEOUT = 20

# Words that make a useless image search ("which", "country", "the") — the
# signal is in the proper nouns, not the scaffolding.
STOP = {
    "which", "what", "who", "where", "when", "how", "is", "are", "was", "were",
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "most",
    "least", "many", "much", "does", "do", "did", "has", "have", "had", "world",
    "country", "countries", "state", "states", "city", "cities", "people",
    "only", "these", "this", "that", "one", "two", "three", "us", "usa",
    "american", "americans", "united", "you", "your", "it", "its", "not",
    "about", "more", "than", "first", "last", "name", "called", "known",
}


# ── Ken Burns ─────────────────────────────────────────────────────────────────
# A still that slowly drifts reads as a real shot rather than a slide, without
# the legibility and bandwidth costs of actual video.
#
# Both the chart render and build_video draw this same photo (the chart carries
# the slice that sits behind it), so the drift MUST be one deterministic function
# of time that both call. If only one of them moved, the seam between them would
# reopen on every frame.
KB_ZOOM = 1.08          # ends 8% closer than it starts


def kb_base(path: str):
    """The image at maximum zoom; every frame is then just a crop of it.

    fetch() already saves at this size (downscaled from the Pexels original), so
    normally there is nothing to do here — resizing is only a safety net for an
    image that came from somewhere else. Scaling UP here is what we must avoid:
    it is what made the background soft.
    """
    from PIL import Image
    img = Image.open(path).convert("RGB")
    tw, th = int(W * KB_ZOOM), int(H * KB_ZOOM)
    if (img.width, img.height) != (tw, th):
        img = img.resize((tw, th), Image.LANCZOS)
    return img


KB_STEPS = 8            # drift updates per second
_kb_cache: dict = {}    # one slot per (base, quantised t) — frames arrive in order


def kb_frame(base, t: float, duration: float):
    """The 1080x1920 frame of the drift at time t.

    Rebuilding a full-res frame per video frame was costing ~74ms x 1300 frames
    x2 (chart + background) and blew the render past ten minutes. The pan is slow
    enough that 8 updates/second is indistinguishable from 24, so t is quantised
    and the last result reused. Both callers quantise identically, so the chart's
    slice and the frame background stay locked to the same image.
    """
    from PIL import Image
    p  = 0.0 if duration <= 0 else min(max(t / duration, 0.0), 1.0)
    pq = round(p * duration * KB_STEPS) / KB_STEPS / max(duration, 1e-9)   # quantise
    pq = min(max(pq, 0.0), 1.0)

    ck = (id(base), round(pq, 6))
    hit = _kb_cache.get(ck)
    if hit is not None:
        return hit

    z = 1.0 + (KB_ZOOM - 1.0) * pq                      # 1.00 -> 1.08
    ww, hh = int(W * KB_ZOOM / z), int(H * KB_ZOOM / z)
    maxx, maxy = base.width - ww, base.height - hh
    x = int(maxx * (0.35 + 0.30 * pq))                  # gentle pan while zooming
    y = int(maxy * (0.30 + 0.40 * pq))
    img = base.crop((x, y, x + ww, y + hh)).resize((W, H), Image.BILINEAR)

    _kb_cache.clear()                                   # frames are sequential
    _kb_cache[ck] = img
    return img


# Scenes for questions with nothing photographable in them (riddles, "would you
# rather", pure-number answers).
CONCEPT_QUERY = {
    "riddles":   "misty forest mystery",
    "wyr":       "forked path crossroads",
    "odds":      "dice casino",
    "trick":     "optical illusion pattern",
    "body":      "human anatomy",
    "money":     "cash money",
    "price":     "shopping store",
    "space":     "galaxy stars",
    "tech":      "technology circuit",
    "food":      "food table",
    "animals":   "wildlife nature",
    "geography": "world map globe",
    "history":   "ancient ruins",
    "sports":    "stadium sport",
    "automotive": "classic sports car",
}


def _key() -> str:
    k = os.environ.get("PEXELS_API_KEY", "").strip()
    if not k:
        f = Path(__file__).parent / "pexels_api.txt"
        if f.exists():
            k = f.read_text(encoding="utf-8").strip()
    return k


def _used() -> list:
    if USED.exists():
        try:
            return json.loads(USED.read_text(encoding="utf-8")).get("ids", [])
        except Exception:
            return []
    return []


def _remember(pid: int) -> None:
    ids = _used()
    ids.append(pid)
    USED.write_text(json.dumps({"ids": ids[-KEEP:]}), encoding="utf-8")


# Words that survive the stop-list but name no photographable thing: comparatives
# ("taller"), quantity/relation fillers ("without", "share", "worth"), and the
# like. Left in, they become the search term for a question whose real subject is
# its own answer — and a query like "taller" or "drinking" returns people, not a
# topic. Gerund/participle verbs (-ing / -ed) are caught by rule, not listed here.
NON_SUBJECT = {
    "without", "within", "whole", "share", "reach", "stretch", "worth", "cost",
    "costs", "value", "amount", "number", "fraction", "percent", "percentage",
    "taller", "shorter", "longer", "higher", "lower", "bigger", "smaller",
    "faster", "slower", "deeper", "closer", "heavier", "lighter", "older",
    "younger", "morning", "evening", "every", "never", "always", "roughly",
    "nearly", "inside", "outside", "between", "before", "after", "during",
    "actually", "really", "almost", "enough", "still", "even",
}


def _is_subject(word: str) -> bool:
    """True if the word could plausibly be photographed. A gerund or past-tense
    verb ("drinking", "melted") and the comparatives/fillers above are things a
    photo cannot depict, so they must not become the search term."""
    lw = word.lower()
    if lw in NON_SUBJECT:
        return False
    if lw.endswith("ing") or lw.endswith("ed"):
        return False
    return len(word) > 3


def query_for(question: str, options: list, concept: str, fmt: str = "trivia") -> str:
    """Photo search terms for a question — WITHOUT giving the answer away.

    The obvious idea is to search on the answer, and it is wrong: "The Statue of
    Liberty was a gift from which country?" -> "France" -> an Eiffel Tower behind
    the question, and the quiz is over before the countdown starts. The channels
    winning this format use backgrounds that say nothing about the answer, and
    that is not laziness on their part.

    So: search the question's own subject, with every word that appears in ANY
    option stripped out — the distractors are as spoiling as the answer, since a
    photo of Paris narrows three choices to one. A question that names nothing
    photographable (riddles, would-you-rather) falls back to a scene for the topic.
    """
    # A riddle or a would-you-rather describes nothing photographable at all —
    # "What gets wetter the more it dries?" has no subject, and mining it for
    # nouns just yields "wetter dries". Go straight to a scene for the topic.
    if fmt in ("riddle", "wyr"):
        return CONCEPT_QUERY.get(concept, concept or "landscape")

    banned = set(STOP)
    for opt in (options or []):
        for w in re.sub(r"[^A-Za-z ]", " ", str(opt)).split():
            banned.add(w.lower())

    tokens = re.sub(r"[^A-Za-z ]", " ", question).split()
    cands  = [(i, w) for i, w in enumerate(tokens)
              if w.lower() not in banned and len(w) > 3]

    # A proper noun is the signal that the question HAS a subject worth showing.
    # The first word of a sentence is always capitalised, so it proves nothing and
    # must be excluded — otherwise every question looks like it names something and
    # would-you-rather ends up searching Pexels for "every sleep".
    proper = [w for i, w in cands if i > 0 and w[0].isupper()]
    if proper:
        # prefer the named thing ("Statue Liberty"), longest first
        return " ".join(sorted(proper, key=len, reverse=True)[:2])
    # The common-noun path grabs the longest leftover words, and when the real
    # subject is the ANSWER (so it is banned), all that is left is verbs and
    # comparatives: "Which animal ... without drinking water?" -> "drinking
    # without" -> a bar full of cocktails and people. A guessed subject is worse
    # than none, so a token that is not a photographable thing (a gerund/participle
    # verb, or a comparative/filler word) disqualifies itself, and if nothing
    # concrete survives we use the curated topic scene instead.
    common = [w for _, w in cands if _is_subject(w)]
    if common:
        best = sorted(common, key=len, reverse=True)[:2]
        # a bare noun like "baseball" or "food" is a fine, spoiler-free subject
        if any(len(w) > 4 for w in best):
            return " ".join(best)
    return CONCEPT_QUERY.get(concept, concept or "landscape")


# Pexels 403s urllib's default User-Agent — it must look like a browser.
UA = "Mozilla/5.0 (compatible; Quizora/1.0)"

# A stranger's face behind the question is the worst possible background: the eye
# goes to the face, not the quiz, and it makes the video look like a random stock
# photo was slapped on — which it was. A search for "potatoes" returned a man
# sitting on potato sacks and his head landed directly behind the question card.
#
# Pexels gives every photo a descriptive `alt`, and it says so plainly ("A man
# sits with bags of potatoes"), so we can just read it. In that same result set
# eight clean potato photos were available — we simply picked the wrong one.
PEOPLE_WORDS = {
    "man", "men", "woman", "women", "person", "people", "boy", "girl", "child",
    "children", "kid", "kids", "lady", "guy", "human", "portrait", "face", "hand",
    "hands", "holding", "sitting", "standing", "wearing", "model", "selfie",
    "couple", "family", "worker", "chef", "someone", "male", "female", "posing",
    "smiling", "young", "adult", "gentleman", "businessman",
    # A "drinking"-style query returns bars and cafes whose alt text names the
    # group, not "man"/"woman": "Two friends clinking beer bottles", "A
    # fashionable individual sips a drink", "Two adults enjoying red wine".
    "adults", "friend", "friends", "individual", "teen", "teens", "teenager",
    "teenagers", "crowd", "group", "colleague", "colleagues", "player", "players",
    "customer", "customers", "diner", "diners", "drinker", "drinkers", "enjoying",
    "sips", "everyone", "somebody", "himself", "herself",
}


def _has_people(photo: dict) -> bool:
    alt = (photo.get("alt") or "").lower()
    words = set(re.sub(r"[^a-z ]", " ", alt).split())
    return bool(words & PEOPLE_WORDS)


def _search(query: str, key: str) -> list:
    url = ("https://api.pexels.com/v1/search?"
           + urllib.parse.urlencode({"query": query, "orientation": "portrait",
                                     "per_page": 15, "size": "large"}))
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r).get("photos", [])


def fetch(question: str, options: list, concept: str, out_path: str,
          fmt: str = "trivia", query_override: str = "") -> str | None:
    """Download a relevant portrait photo, cropped to frame and darkened so the
    question card stays readable. Returns the path, or None to use the dark
    canvas (no key, no result, or every candidate used recently).

    query_override: a curated spoiler-free search term (the bank's image_query).
    When present it is used verbatim instead of the query_for() heuristic, which
    mangles fact-style questions ("...Leaning Tower of Pisa?" -> "Leaning Indian").
    The people filter and recency de-dup still apply."""
    key = _key()
    if not key:
        print("[BG] no PEXELS_API_KEY — keeping the dark canvas")
        return None

    query = (query_override or "").strip() or query_for(question, options, concept, fmt)
    try:
        photos = _search(query, key)
        if not photos:                      # nothing for e.g. "Aramaic" — widen
            photos = _search(concept or "landscape", key)
        if not photos:
            print(f"[BG] no photo for '{query}'")
            return None

        # Scenery and objects only — never a person behind the question card.
        clean = [p for p in photos if not _has_people(p)]
        if not clean:
            # every result is a photo of somebody; a topic scene beats a stranger's face
            print(f"[BG] every '{query}' result has people in it — using the {concept} scene")
            photos = _search(CONCEPT_QUERY.get(concept, concept or "landscape"), key)
            clean  = [p for p in photos if not _has_people(p)] or photos
        photos = clean

        recent = set(_used())
        fresh  = [p for p in photos if p["id"] not in recent] or photos
        pick   = random.choice(fresh[:8])

        # Take the ORIGINAL, not "portrait". Pexels' portrait size is 800x1200 —
        # filling a 1080x1920 frame from that is a 1.6x upscale, and Ken Burns
        # then upscales a further 1.08x, so the background came out visibly soft.
        # The original is typically 4000px+, so we downscale instead, which is
        # sharp. It costs ~1MB per render, which is nothing.
        src = pick["src"].get("original") or pick["src"].get("large2x") or pick["src"]["large"]
        dl  = urllib.request.Request(src, headers={"User-Agent": UA})
        with urllib.request.urlopen(dl, timeout=TIMEOUT) as r:
            raw = r.read()

        from PIL import Image, ImageEnhance
        import io
        img = Image.open(io.BytesIO(raw)).convert("RGB")

        # Cover-crop straight to the Ken Burns base size, so kb_base never has to
        # scale the image up again.
        tw, th = int(W * KB_ZOOM), int(H * KB_ZOOM)
        scale  = max(tw / img.width, th / img.height)
        img    = img.resize((max(tw, int(img.width * scale)), max(th, int(img.height * scale))),
                            Image.LANCZOS)
        left, top = (img.width - tw) // 2, (img.height - th) // 2
        img = img.crop((left, top, left + tw, top + th))

        # Every word now sits on an opaque card, so the photo no longer has to be
        # crushed for legibility — only the burned-in captions ride directly on
        # it. A light touch keeps the background vivid instead of grey.
        img = ImageEnhance.Brightness(img).enhance(0.86)
        img = ImageEnhance.Color(img).enhance(1.12)

        img.save(out_path, "JPEG", quality=94, subsampling=0)
        _remember(pick["id"])
        print(f"[BG] '{query}' -> pexels #{pick['id']} by {pick.get('photographer','?')}")
        return out_path
    except Exception as e:
        print(f"[BG] skipped ({e}) — keeping the dark canvas")
        return None
