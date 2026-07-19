# -*- coding: utf-8 -*-
"""
BrainBolt — quiz/game Shorts pipeline (adapted from The World in Charts).
Viral data comparisons as animated charts. Topics/renderers live in charts.py.
3 posts/day; scheduler is cron-job.org → GitHub Actions (chart.yml).

Changelog v7:
  - Option B architecture: Gemini generates unique narration + title each run
    using exact numbers computed by code — chart and voiceover always match
  - Financial constants centralised in AU_FINANCE_CONSTANTS — update once yearly
  - SG rate corrected to 12% (was 0.115 — now current July 2025 rate)
  - num_to_words() converts figures to spoken English for TTS
  - compute_anim_numbers() returns all chart values for Gemini prompt injection
  - generate_anim_script() calls Gemini for unique narration/title per run
"""

__version__ = "7.0.0"

import os, re, json, asyncio, hashlib, datetime, tempfile, random, math, copy
from pathlib import Path
from quality_scorer import score_pipeline_output
from shared import add_to_ledger as _add_to_topic_ledger
from affiliates import build_affiliate_block, comment_text as affiliate_comment_text

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.ticker
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from google import genai
from moviepy.editor import (
    VideoFileClip, AudioFileClip, ImageClip,
    CompositeVideoClip, ColorClip, VideoClip,
)
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# ── Constants ──────────────────────────────────────────────────────────────────
W, H           = 1080, 1920
FPS            = 24
AU_VOICE       = "en-US-ChristopherNeural"   # legacy default
# Per-video voice variation — mirrors pipeline.py so the two pipelines don't
# sound like two different channels
AU_VOICES      = ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]  # rotate M/F Hinglish voices
VOICE_RATES    = ["+5%", "+7%"]  # +10 rushed (viewer report)
DISCLAIMER     = "General-knowledge entertainment. Answers verified before posting."
DEFAULT_ACCENT = (0, 190, 160)

# matplotlib chart area — taller to fill portrait frame better
CHART_W_PX = 1020
CHART_H_PX = 1400

def _preflight_gemini(key: str) -> None:
    """Exit early if ALL Gemini models are quota-exhausted — saves a full GH Actions job."""
    client = genai.Client(api_key=key)
    for model in GEMINI_MODEL_CHAIN:
        try:
            client.models.generate_content(
                model=model,
                contents="hi",
                config=genai.types.GenerateContentConfig(max_output_tokens=1),
            )
            return  # at least one model has quota — proceed
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "ResourceExhausted" in type(e).__name__:
                continue  # this model is exhausted, try next
            return  # non-quota error — let the pipeline handle it naturally
    raise SystemExit(
        "[Gemini] All models quota-exhausted — free tier resets at midnight UTC. "
        "Re-trigger workflow after reset."
    )


# Gemini model chain — tries in order on rate limit
GEMINI_MODEL_CHAIN = [
    "gemini-flash-lite-latest",   # new accounts only get -latest aliases + Gemini 3
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
]


from charts import CONCEPT_PLAYLISTS, DEFAULT_PLAYLIST


def _normalize_playlist_title(t: str) -> str:
    """Casefold + unify dashes + collapse whitespace — encoding drift on
    em-dashes caused duplicate playlists on channel 1."""
    t = t.replace("—", "-").replace("–", "-").replace("‒", "-")
    return " ".join(t.split()).casefold()


def _get_or_create_playlist(yt, title: str, map_path) -> str | None:
    from pathlib import Path as _P
    import json as _j
    map_path = _P(map_path)
    pmap: dict = {}
    if map_path.exists():
        try:
            pmap = _j.loads(map_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if title in pmap:
        return pmap[title]
    # Search ALL existing channel playlists first (paginated, normalized titles) —
    # prevents duplicates across fresh CI runs where the local map cache is absent.
    try:
        want = _normalize_playlist_title(title)
        page = None
        while True:
            resp = yt.playlists().list(part="snippet", mine=True, maxResults=50,
                                       pageToken=page).execute()
            for item in resp.get("items", []):
                if _normalize_playlist_title(item["snippet"]["title"]) == want:
                    pid = item["id"]
                    pmap[title] = pid
                    map_path.write_text(_j.dumps(pmap, indent=2), encoding="utf-8")
                    print(f"[Playlist] Found existing '{title}' ({pid})")
                    return pid
            page = resp.get("nextPageToken")
            if not page:
                break
    except Exception as e:
        # Never create on a failed search — a duplicate playlist is worse than
        # one video missing its playlist (it gets re-filed on a later run).
        print(f"[Playlist] API search failed: {e} — skipping playlist add this run")
        return None
    # Only create if genuinely not found
    try:
        resp = yt.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": "Roz naye ajab gajab facts. Pata tha? Comment mein batao!",
                },
                "status": {"privacyStatus": "public"},
            },
        ).execute()
        pid = resp["id"]
        pmap[title] = pid
        map_path.write_text(_j.dumps(pmap, indent=2), encoding="utf-8")
        print(f"[Playlist] Created '{title}' ({pid})")
        return pid
    except Exception as e:
        print(f"[Playlist] Create failed: {e}")
        return None


def _add_to_playlist(yt, vid_id: str, playlist_id: str) -> None:
    # YouTube 409s ("operation was aborted") when inserting into a
    # just-created playlist — retry with backoff (hit on first epoch-2 post).
    import time as _t
    for _attempt in range(3):
        try:
            yt.playlistItems().insert(
                part="snippet",
                body={"snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": vid_id},
                }},
            ).execute()
            print(f"[Playlist] Added {vid_id} to playlist {playlist_id}")
            return
        except Exception as e:
            if _attempt < 2 and ("409" in str(e) or "aborted" in str(e).lower()):
                print(f"[Playlist] Add got 409 — retrying in 5s ({_attempt + 1}/3)")
                _t.sleep(5)
                continue
            print(f"[Playlist] Add failed: {e}")
            return


def _post_pinned_comment(yt, vid_id: str, meta: dict) -> None:
    """Post a creator disclaimer comment. Surfaces prominently as channel-owner comment."""
    import datetime as _dt
    today_str = _dt.date.today().strftime("%d %B %Y").lstrip("0")  # %-d is Linux-only
    text = (
        f"Answers check karke post kiye hain (as at {today_str}). Koi galat lage? "
        f"Neeche batao — best correction pin hogi. Pata tha? Comment karo!"
    )
    try:
        yt.commentThreads().insert(
            part="snippet",
            body={"snippet": {
                "videoId": vid_id,
                "topLevelComment": {"snippet": {"textOriginal": text}},
            }},
        ).execute()
        print(f"[Comment] Posted creator comment on {vid_id}")
    except Exception as e:
        print(f"[Comment] Skipped (re-run auth_setup.py to add youtube.force-ssl scope): {e}")


def _post_affiliate_comment(yt, vid_id: str, concept: str) -> None:
    """Dedicated affiliate comment — URL alone on its own line for easy
    long-press copying (Shorts comments render links unclickable)."""
    text = affiliate_comment_text(concept)
    if not text:
        return
    try:
        yt.commentThreads().insert(
            part="snippet",
            body={"snippet": {
                "videoId": vid_id,
                "topLevelComment": {"snippet": {"textOriginal": text}},
            }},
        ).execute()
        print(f"[Comment] Posted affiliate comment on {vid_id}")
    except Exception as e:
        print(f"[Comment] Affiliate comment skipped: {e}")


# First 3 hashtags surface above the title in the Shorts UI — keep one brand
# tag + two Devanagari tags there so the visible strip reads Hindi.
_HASHTAGS = (
    "#AjabGajabFacts #रोचकतथ्य #अजबगजब #AmazingFacts #FactsInHindi #HindiFacts "
    "#हिंदीफैक्ट्स #GKFacts #IndiaFacts #DidYouKnow #RochakTathya #Facts #GK "
    "#Shorts #YTShortsIndia"
)

_CORE_TAGS = [
    "ajab gajab facts", "amazing facts", "facts in hindi", "hindi facts",
    "rochak tathya", "gk in hindi", "india facts", "did you know",
    "interesting facts", "gk quiz hindi", "hinglish facts", "daily facts",
    "shorts", "रोचक तथ्य", "अजब गजब", "हिंदी में जानकारी", "जीके क्विज",
]


def _post_engagement_comment(yt, vid_id: str, title: str) -> None:
    t = title.lower()
    if "would you rather" in t:
        q = "Drop your three picks — one word each. Wrong answers welcome."
    elif "riddle" in t:
        q = "No googling. How many did you solve? Be honest."
    elif "price" in t or "$" in t:
        q = "How far off were your guesses? Closest comment wins bragging rights."
    else:
        q = "Ye fact aapko pehle se pata tha? YES ya NO — comment karo!"
    try:
        yt.commentThreads().insert(
            part="snippet",
            body={"snippet": {"videoId": vid_id, "topLevelComment": {
                "snippet": {"textOriginal": q}
            }}},
        ).execute()
        print(f"[YouTube] OK First comment: {q[:60]}")
    except Exception as e:
        print(f"[YouTube] First comment skipped: {e}")


# ── Daily seed ─────────────────────────────────────────────────────────────────
def daily_seed(channel_id: str) -> int:
    today = datetime.date.today().isoformat()
    return int(hashlib.md5(f"animated-{today}-{channel_id}".encode()).hexdigest()[:8], 16)


# ── Fonts ──────────────────────────────────────────────────────────────────────
def load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Cross-platform font loader."""
    weight   = "Bold" if bold else "Regular"
    weight_l = "bold" if bold else ""
    candidates = [
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{weight}.ttf",
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/System/Library/Fonts/Supplemental/Arial{' Bold' if bold else ''}.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        f"C:/Windows/Fonts/arial{weight_l}.ttf",
        f"C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        f"C:/Windows/Fonts/segoeui{weight_l}.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    try:
        from PIL import __file__ as pil_init
        bundled = Path(pil_init).parent / "fonts" / "DejaVuSans.ttf"
        if bundled.exists():
            return ImageFont.truetype(str(bundled), size)
    except Exception:
        pass
    print(f"⚠️  No scalable font found — text will render tiny!")
    return ImageFont.load_default()


def wrap_text(text: str, font, max_w: int) -> list:
    words = text.split()
    lines, cur = [], []
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for w in words:
        test = " ".join(cur + [w])
        bb   = dummy.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


# ── Number to spoken English ──────────────────────────────────────────────────
def num_to_words(n: float, is_money: bool = True, suffix: str = "") -> str:
    """Convert a number to spoken English for TTS narration.
    E.g. 115000 -> 'one hundred and fifteen thousand dollars'"""
    ones = ["", "one", "two", "three", "four", "five", "six", "seven",
            "eight", "nine", "ten", "eleven", "twelve", "thirteen",
            "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty",
            "sixty", "seventy", "eighty", "ninety"]

    def _say(n: int) -> str:
        if n == 0:
            return "zero"
        if n < 0:
            return "minus " + _say(-n)
        if n < 20:
            return ones[n]
        if n < 100:
            t = tens[n // 10]
            o = ones[n % 10]
            return t + (" " + o if o else "")
        if n < 1000:
            h = ones[n // 100] + " hundred"
            rem = n % 100
            return h + (" and " + _say(rem) if rem else "")
        if n < 1_000_000:
            t = _say(n // 1000) + " thousand"
            rem = n % 1000
            return t + (" " + _say(rem) if rem else "")
        t = _say(n // 1_000_000) + " million"
        rem = n % 1_000_000
        return t + (" " + _say(rem) if rem else "")

    n_int = int(round(n))
    words = _say(n_int)
    if is_money:
        words += " dollars"
    if suffix:
        words += " " + suffix
    return words


def pct_to_words(pct: float) -> str:
    """Convert percentage float to spoken English. E.g. 0.12 -> 'twelve percent'
    Handles decimals correctly: 0.095 -> 'nine point five percent'"""
    val = round(pct * 100, 4)
    if val == int(val):
        return num_to_words(int(val), is_money=False) + " percent"
    # E.g. 9.5 -> whole=9 dec_digit=5 -> "nine point five percent"
    # E.g. 9.25 -> whole=9 dec_str="25" -> "nine point two five percent"
    whole    = int(val)
    dec_frac = round(val - whole, 4)
    # Convert fractional part to digit string, drop trailing zeros
    dec_str  = f"{dec_frac:.4f}"[2:].rstrip("0")  # e.g. "5000" -> "5", "2500" -> "25"
    w = num_to_words(whole, is_money=False)
    # Spell out each digit individually for clarity
    digit_words = []
    for ch in dec_str:
        digit_words.append(num_to_words(int(ch), is_money=False))
    d = " ".join(digit_words)
    return w + (" point " + d if d else "") + " percent"


from charts import compute_anim_numbers


# ── Gemini: generate unique narration + title per run ────────────────────────
def generate_anim_script(anim_key: str, numbers: dict,
                          anim_meta: dict, gemini_key: str) -> dict:
    """Call Gemini to write a unique narration using exact computed numbers.
    Returns updated meta dict with fresh title, narration, and description."""
    _genai_client = genai.Client(api_key=gemini_key)

    # Format numbers dict for prompt
    nums_text = "\n".join(f"  {k}: {v}" for k, v in numbers.items())

    regen_hint = os.environ.get("REGEN_HINT", "").strip()
    if regen_hint and datetime.date.today() > datetime.date(2026, 5, 22):
        print("[REGEN_HINT] Campaign expired (past May 22) — ignoring hint")
        regen_hint = ""
    regen_block = (
        f"\nMANDATORY DIRECTION FOR THIS RUN (highest priority):\n{regen_hint}\n"
        if regen_hint else ""
    )

    prompt = f"""You are writing narration for a 35-45 second data-comparison YouTube Short for a global audience.
The video shows an animated chart about: {anim_meta['topic']}
{regen_block}

EXACT FIGURES TO USE (from real public data — do not change these):
{nums_text}

CRITICAL — CHART SYNC RULE: Every specific dollar amount, percentage, or year figure
you cite in the narration must come from the EXACT FIGURES list above.
These figures represent exactly what is visible in the chart.
Do not use your own knowledge to introduce any figure not in this list.
If a figure is not listed above, do not cite it.

RULES:
- Narration must be 85-105 words total (spoken in 32-40 seconds)
- Use ONLY the exact figures provided above — no inventing other numbers
- Plain language — 8th grade reading level
- Name the source casually when it adds punch (e.g. "according to NASA")
- Educational only — no personal financial advice
- End with exactly: "Follow for a new quiz every day."
- FIRST sentence: open with the single most shocking number from the list, framed to challenge intuition (e.g. "31,000 dollars. That is what Ronaldo earns in ONE hour."). Never open with background or a greeting.
- TITLE: put the KEY FIGURE or most surprising number in the FIRST 35 characters — mobile browse cuts off after 35 chars

CRITICAL FORMATTING: All JSON string values must be PLAIN TEXT ONLY.
- NEVER use asterisks (*word*), underscores (_word_), or any markdown in narration or title.
- edge-tts reads these symbols aloud as "asterisk" — it ruins the audio.
- Wrong: "your *earnings* grow faster"  Right: "your earnings grow faster"

Write a fresh unique angle. Do not use generic phrasing.

Return ONLY valid JSON, no markdown:
{{
  "title": "Specific compelling title 35-60 chars — key figure in first 35 chars",
  "narration": "Full narration text 85-105 words using ONLY the provided figures",
  "description": "3-4 sentence YouTube description using the real numbers. End with: General information only, not financial advice. Consult a licensed financial adviser."
}}"""

    MIME_SUPPORTED = set(GEMINI_MODEL_CHAIN)  # all current models support JSON mime

    for model_name in GEMINI_MODEL_CHAIN:
        for _attempt in range(2):  # retry once on empty response
          try:
            gen_cfg   = {
                "temperature": 0.80,
                "max_output_tokens": 1000,
            }
            if model_name in MIME_SUPPORTED:
                gen_cfg["response_mime_type"] = "application/json"
                try:
                    gen_cfg["thinking_config"] = genai.types.ThinkingConfig(thinking_budget=0)
                except AttributeError:
                    pass

            resp  = _genai_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(**gen_cfg),
            )
            raw = resp.text.strip() if resp.text else ""
            if not raw:
                print(f"[Script] {model_name} empty response (attempt {_attempt+1}) - retry")
                continue
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            result = json.loads(raw)
            if all(k in result for k in ("title", "narration", "description")):
                # Ensure word count is reasonable (100-200 words)
                word_count = len(result["narration"].split())
                if word_count < 80 or word_count > 200:
                    print(f"[Script] {model_name} narration word count {word_count} out of range - retry")
                    continue
                # Content safety - no risky financial claims
                risky = ["guaranteed return", "guaranteed profit", "risk-free",
                         "you will earn", "get rich", "secret loophole"]
                narration_lower = result["narration"].lower()
                if any(r in narration_lower for r in risky):
                    print(f"[Script] {model_name} narration failed safety check - retry")
                    continue
                print(f"[Script] {model_name} | {result['title']}")
                return result
          except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "404" in err:
                print(f"[Script] {model_name} rate-limited — skip model")
                break  # break inner loop, try next model
            if "503" in err or "UNAVAILABLE" in err or "ServiceUnavailable" in type(e).__name__:
                print(f"[Script] {model_name} temporarily unavailable — skip model")
                break
            print(f"[Script] {model_name} error: {e}")
            break  # unexpected error — skip model

    # Fallback to hardcoded if all models fail
    print("[Script] All models failed — using hardcoded narration")
    return {
        "title":       anim_meta["title"],
        "narration":   anim_meta["narration"],
        "description": anim_meta["description"],
    }


# ── Animation content ──────────────────────────────────────────────────────────

from charts import ANIMATIONS


# ── Animation ledger — prevents repeating the same type ─────────────────────
ANIM_LEDGER_PATH = Path("anim_ledger.json")


def load_anim_ledger() -> list:
    if not ANIM_LEDGER_PATH.exists():
        return []
    try:
        with open(ANIM_LEDGER_PATH, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return []


def save_anim_ledger(ledger: list) -> None:
    try:
        with open(ANIM_LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(ledger[-30:], f, indent=2)
    except Exception as e:
        print(f"[AnimLedger] Write failed: {e}")


_BUDGET_ANIM_KEYS: list = []   # unused on this channel


def pick_animation_type(channel_id: str, rng) -> str:
    """Pick an animation type not used in the last N runs.
    During budget week (FORCE_NEWS_MODE=1) prefer budget-relevant concepts."""
    ledger     = load_anim_ledger()
    recent     = {e["anim_key"] for e in ledger[-15:]}  # avoid last 15 (3/day)
    all_keys   = list(ANIMATIONS.keys())

    # US-anchored topics stay out of the rotation until the geo tilt is switched
    # on deliberately. Without this they would silently take ~20% of all posts.
    try:
        from charts import US_KEYS
        if os.environ.get("US_TILT") != "1":
            all_keys = [k for k in all_keys if k not in US_KEYS]
        else:
            print(f"[AnimLedger] US_TILT on — {len(US_KEYS)} US topics in rotation")
    except Exception as _ge:
        print(f"[AnimLedger] US gate skipped: {_ge}")

    # Budget week: restrict to budget-relevant concepts first
    import datetime as _dt
    _budget_active = (
        os.environ.get("FORCE_NEWS_MODE") == "1"
        and _dt.date.today() <= _dt.date(2026, 5, 22)
    )
    if _budget_active:
        pool = [k for k in _BUDGET_ANIM_KEYS if k in all_keys and k not in recent]
        if not pool:
            pool = _BUDGET_ANIM_KEYS  # all budget ones used recently, allow repeats
        print(f"[AnimLedger] Budget week — pool: {pool}")
    else:
        pool = [k for k in all_keys if k not in recent]
        if not pool:
            pool = all_keys

    # Performance feedback: retire topics that matured dead and weight the
    # rest by their category's live track record (performance.py). Neutral on
    # any failure — the chooser must never block a post.
    try:
        from performance import category_weights, retired_keys, weight_for_key
        dead  = retired_keys()
        alive = [k for k in pool if k not in dead]
        if alive:
            pool = alive
        weights = category_weights()
        if weights:
            chosen = rng.choices(pool, weights=[weight_for_key(k, weights) for k in pool], k=1)[0]
            print(f"[AnimLedger] Weighted pick ({len(dead)} retired, "
                  f"cat weights {weights}) -> {chosen}")
            return chosen
    except Exception as _pe:
        print(f"[Perf] Weighting skipped: {_pe}")

    chosen = rng.choice(pool)
    print(f"[AnimLedger] Avoided recent: {recent} -> picked: {chosen}")
    return chosen


def log_anim_type(anim_key: str, channel_id: str, quality_score: float = None) -> None:
    ledger = load_anim_ledger()
    entry = {"date": datetime.date.today().isoformat(), "channel_id": channel_id, "anim_key": anim_key}
    if quality_score is not None:
        entry["quality_score"] = round(quality_score, 2)
    ledger.append(entry)
    save_anim_ledger(ledger)


# ── matplotlib theme ──────────────────────────────────────────────────────────
def setup_dark_axes(ax) -> None:
    ax.set_facecolor("#0C0E1C")
    ax.tick_params(colors="white", labelsize=11)
    for spine in ax.spines.values():
        spine.set_color("#333355")
    ax.yaxis.label.set_color("white")
    ax.xaxis.label.set_color("white")
    ax.title.set_color("white")
    ax.grid(True, color="#1A1A3A", linewidth=0.8, alpha=0.6)


def accent_hex(accent: tuple) -> str:
    return "#{:02X}{:02X}{:02X}".format(*accent)


from charts import RENDERERS


# ── Hinglish localisation ────────────────────────────────────────────────────
def localize_segments_hinglish(segs, gemini_key):
    """Translate each segment's English text into spoken Devanagari-Hinglish,
    PRESERVING segment count and order — so the sentence-mark sync still lines up
    (segment_starts matches word counts against the Hinglish marks). Hindi words
    in Devanagari; proper nouns / option words / English terms kept as-is. Falls
    back to the English segments on any failure, so a bad Gemini run never blocks
    a post."""
    if not gemini_key or not segs:
        return segs
    texts = [t for (_k, _q, t) in segs]
    prompt = (
        "Translate each English quiz-narration line into natural spoken HINGLISH "
        "for an Indian YouTube Shorts voiceover.\n"
        "Rules:\n"
        "- Write ALL Hindi words in DEVANAGARI script (Hindi लिपि), NEVER romanised. "
        "Write 'सबसे ऊँचा', never 'sabse uncha'.\n"
        "- KEEP proper nouns, place names, the answer option words, and English "
        "terms (question, comment, follow) in English/Roman exactly as written.\n"
        "- Same meaning, punchy and spoken, a bit SHORTER if you can. Do NOT add, "
        "drop, merge or reorder lines.\n"
        "- Return ONLY a JSON array of strings, same count and order as the input.\n\n"
        "Example line: 'Question 1. इनमें से कौन सा monument सबसे ऊँचा है? "
        "Taj Mahal, Gateway of India, या Hawa Mahal?'\n\n"
        "Input lines (JSON):\n" + json.dumps(texts, ensure_ascii=False)
    )
    try:
        client = genai.Client(api_key=gemini_key)
        for model in GEMINI_MODEL_CHAIN:
            try:
                resp = client.models.generate_content(
                    model=model, contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        temperature=0.6, max_output_tokens=3000,
                        response_mime_type="application/json"))
                out = json.loads((resp.text or "").strip())
                if isinstance(out, list) and len(out) == len(segs):
                    return [(k, q, (str(out[i]).strip() or t))
                            for i, (k, q, t) in enumerate(segs)]
                print("[Hinglish] line count mismatch — keeping English")
            except Exception:
                continue
    except Exception as e:
        print(f"[Hinglish] localise failed ({e}) — keeping English")
    return segs


# ── Voiceover ──────────────────────────────────────────────────────────────────
async def generate_voiceover(text: str, out_path: str,
                             voice: str = None, rate: str = None) -> tuple:
    """Returns (duration, marks).

    duration is measured from the saved file. marks are edge-tts
    SentenceBoundary events [(start_s, dur_s, text)] — the real speech timeline,
    which the chart/SFX/captions use so they land on the spoken word instead of
    a word-count guess. The list is empty if the voice emits no boundary events;
    every consumer falls back to word share in that case.
    """
    import re as _re, random as _rnd, datetime as _dt
    # Strip markdown formatting that edge-tts reads aloud as literal symbols
    # e.g. *earnings* -> earnings, **bold** -> bold, _italic_ -> italic
    text = _re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = _re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    text = _re.sub(r'`([^`]+)`', r'\1', text)
    # Expand abbreviated units edge-tts mispronounces ("70c" -> "70 cents")
    text = _re.sub(r'\b(\d+)\s*c\b', r'\1 cents', text)
    text = _re.sub(r'/\s*hr\b', ' per hour', text)
    text = _re.sub(r'/\s*km\b', ' per kilometre', text)
    text = _re.sub(r'/\s*yr\b', ' per year', text)
    # Deterministic per-day voice/rate variation (same seed pattern as jitter)
    _vr = _rnd.Random(_dt.date.today().toordinal() * 17)
    voice = voice or _vr.choice(AU_VOICES)
    rate  = rate or _vr.choice(VOICE_RATES)
    print(f"[Voice] {voice} rate={rate}")
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    audio_data  = bytearray()
    marks       = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
        elif chunk["type"] == "SentenceBoundary":
            # offsets/durations arrive in 100-nanosecond ticks
            marks.append((chunk["offset"] / 1e7, chunk["duration"] / 1e7, chunk["text"]))

    with open(out_path, "wb") as f:
        f.write(bytes(audio_data))

    # Read actual audio duration from the saved MP3 file
    try:
        tmp_clip = AudioFileClip(out_path)
        duration = tmp_clip.duration
        tmp_clip.close()
    except Exception as e:
        print(f"[Voice] Could not measure duration: {e}")
        duration = 0.0

    print(f"[Voice] {duration:.1f}s narration, {len(marks)} sentence marks")
    return duration, marks


# ── Overlay frames ────────────────────────────────────────────────────────────
def frame_title_card(title: str, accent: tuple) -> np.ndarray:
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Much bigger title font for animated videos
    font = load_font(82)
    lines = wrap_text(title, font, W - 80)
    lh    = 100
    total = len(lines) * lh
    y0    = int(H * 0.06)

    # Strong accent bar
    draw.rectangle([(0, y0 - 24), (18, y0 + total + 24)], fill=(*accent, 255))
    # Solid backing, more opaque for prominence
    draw.rounded_rectangle(
        [22, y0 - 28, W - 22, y0 + total + 28],
        radius=22, fill=(0, 0, 0, 200),
    )
    y = y0
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        x  = (W - (bb[2] - bb[0])) // 2
        # Triple shadow for readability
        draw.text((x + 4, y + 4), line, font=font, fill=(0, 0, 0, 220))
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += lh
    return np.array(img)


def frame_disclaimer_bar(text: str) -> np.ndarray:
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(28, bold=False)
    lines = wrap_text(text, font, W - 80)
    lh    = 34
    total = len(lines) * lh
    y0    = H - total - 52
    draw.rounded_rectangle(
        [40, y0 - 14, W - 40, y0 + total + 14],
        radius=12, fill=(0, 0, 0, 175),
    )
    y = y0
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        draw.text(
            ((W - (bb[2] - bb[0])) // 2, y),
            line, font=font, fill=(170, 170, 170, 255),
        )
        y += lh
    return np.array(img)


def frame_cta_animated(text: str, accent: tuple) -> np.ndarray:
    """CTA box for animated videos — placed above disclaimer."""
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(54)
    lines = wrap_text(text, font, W - 140)
    lh    = 68
    total = len(lines) * lh
    y0    = int(H * 0.72) - total // 2

    draw.rounded_rectangle(
        [40, y0 - 28, W - 40, y0 + total + 28],
        radius=22, fill=(*accent, 230),
    )
    y = y0
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        x  = (W - (bb[2] - bb[0])) // 2
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += lh
    return np.array(img)


def frame_end_card_anim(accent: tuple) -> np.ndarray:
    """1.5s branded end card for animated videos."""
    img  = Image.new("RGB", (W, H), (8, 10, 20))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (W, 12)], fill=(*accent,))
    draw.rectangle([(0, H - 12), (W, H)], fill=(*accent,))

    font  = load_font(72)
    title = "Ajab Gajab Facts"
    lines = wrap_text(title, font, W - 120)
    lh    = 90
    total = len(lines) * lh
    y     = H // 2 - total // 2 - 30
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        x  = (W - (bb[2] - bb[0])) // 2
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += lh

    tag_font = load_font(38, bold=False)
    tagline  = "Roz Naye Ajab Gajab Facts."
    tag_bb   = draw.textbbox((0, 0), tagline, font=tag_font)
    tag_x    = (W - (tag_bb[2] - tag_bb[0])) // 2
    tag_y    = H // 2 + total // 2 + 20
    draw.text((tag_x, tag_y), tagline, font=tag_font, fill=(*accent, 220))
    return np.array(img)


# ── Video assembly ────────────────────────────────────────────────────────────
def build_video(
    chart_path: str,
    audio_path: str,
    audio_duration: float,
    anim_meta: dict,
    out_path: str,
    accent: tuple,
    marks: list = None,
    bg_image: str = None,
    quiz_format: str = "trivia",
    captions: list = None,
    cta_text: str = None,
    cta_end: float = None,
) -> None:
    """captions: optional [(text, start, end)] — DISPLAY text per narration
    segment, timed by the real TTS segment boundaries. Used when the SPOKEN
    text must not be drawn: the Hinglish channel speaks Devanagari, which PIL
    cannot shape (no Indic shaping -> tofu/broken matras even with a font
    installed), so the burned-in captions show the Roman-Hinglish card text
    instead. When absent, captions fall back to the spoken marks/narration."""
    audio          = AudioFileClip(audio_path)
    duration       = audio.duration
    chart_clip_raw = VideoFileClip(chart_path).without_audio()

    print(f"[Video] audio={audio.duration:.1f}s chart={chart_clip_raw.duration:.1f}s")

    # Chart was rendered to exactly match audio duration — just trim by 0.1s safety margin
    safe_dur   = min(duration, chart_clip_raw.duration) - 0.1
    chart_clip = chart_clip_raw.subclip(0, max(safe_dur, duration * 0.95))

    # Scale to fill portrait width
    # chart_y = 0.13 places chart at y=249px — only 45px below mini-label bottom (~204px)
    # Previously 0.20 = 384px created a 180px dead gap that looked bad on mobile
    sc         = W / chart_clip.w
    chart_clip = chart_clip.resize(sc)
    chart_y    = int(H * 0.13)

    # Photo background across the full frame; the chart carries the matching
    # slice of the same photo (charts.CHART_BAND). Both drift through the SAME
    # backgrounds.kb_frame, so the two copies stay locked together — if only one
    # of them moved, the seam between them would reopen on every frame.
    bg = None
    if bg_image and Path(bg_image).exists():
        try:
            from backgrounds import kb_base, kb_frame
            import numpy as _np
            _kb = kb_base(bg_image)
            # Drive the drift with audio_duration, NOT duration: mix_quiz_sfx
            # re-encodes the mp3 after audio_duration was measured, so the file is
            # a few hundredths longer. The chart was rendered against
            # audio_duration, and feeding a different length here slides this copy
            # of the photo out of step with the chart's copy — a 1px seam by the
            # end of the video.
            bg = VideoClip(lambda t: _np.asarray(kb_frame(_kb, t, audio_duration)),
                           duration=duration)
        except Exception as _ke:
            # the file is saved at the Ken Burns base size, so it must be scaled
            # back to the frame if we are not drifting it
            print(f"[Video] ken burns skipped: {_ke}")
            bg = ImageClip(bg_image).resize((W, H)).set_duration(duration)
    if bg is None:
        bg = ColorClip((W, H), color=(12, 14, 28)).set_duration(duration)

    layers = [
        bg,
        chart_clip.set_position(("center", chart_y)).set_duration(duration),
    ]

    def il(arr, start, dur):
        return (
            ImageClip(arr, ismask=False)
            .set_start(start)
            .set_duration(max(dur, 0.12))
        )

    def frame_mini_label(title: str, accent: tuple) -> np.ndarray:
        img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = load_font(36, bold=False)
        short = title if len(title) <= 45 else title[:42] + "..."
        bb    = draw.textbbox((0, 0), short, font=font)
        tw    = bb[2] - bb[0]
        x     = (W - tw) // 2
        y     = int(H * 0.08)
        draw.rounded_rectangle(
            [x - 20, y - 8, x + tw + 20, y + (bb[3] - bb[1]) + 8],
            radius=8, fill=(0, 0, 0, 140),
        )
        draw.text((x + 2, y + 2), short, font=font, fill=(0, 0, 0, 160))
        draw.text((x, y), short, font=font, fill=(*accent, 220))
        return np.array(img)

    def frame_caption_anim(text: str, accent: tuple) -> np.ndarray:
        """Bottom caption strip (band below the chart) — Shorts are mostly
        watched muted, so the narration must be readable."""
        img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # 52px + anchored at 84.5%: the old 42px band at 90.5% sat inside the
        # Shorts UI overlay (video title/channel row paints over the bottom
        # ~12% on phones) — captions were partially covered for real viewers.
        font = load_font(52)
        lines = wrap_text(text, font, W - 140)[:2]
        lh    = 68
        y0    = int(H * 0.845) - (len(lines) * lh) // 2
        for j, line in enumerate(lines):
            bb = draw.textbbox((0, 0), line, font=font)
            tw = bb[2] - bb[0]
            x  = (W - tw) // 2
            y  = y0 + j * lh
            draw.rounded_rectangle([x - 18, y - 6, x + tw + 18, y + lh - 8],
                                   radius=8, fill=(0, 0, 0, 150))
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 170))
            draw.text((x, y), line, font=font, fill=(255, 255, 255))
        return np.array(img)

    # Retention/loop engineering: the answer reveal must own the final
    # seconds — the algorithm's expansion gate is average view duration, and
    # every second of overlay clutter at the end invites a swipe. Ending on
    # the reveal also makes the Shorts auto-loop land back on question 1
    # like an intentional reset (rewatch signal).
    disclaimer_start = max(duration - 2.2, 0)
    cta_start        = max(disclaimer_start - 2.8, duration * 0.75)

    # Burned-in captions. When the TTS gave us real sentence offsets, each chunk
    # is timed inside its own sentence, so any residual error is bounded by one
    # sentence instead of accumulating across the whole script. Word share is
    # the fallback (it trails the voice by seconds — see charts.segment_starts).
    # Captions stop at the disclaimer bar to avoid stacking in the bottom band.
    try:
        _n = 0
        if captions:
            # Pre-timed Roman display text (one entry per narration segment).
            # Chunk each segment's text into 7-word pieces spread across its
            # real window, so pacing still tracks the voice.
            for _txt, _cs, _ce in captions:
                _cs, _ce = float(_cs), min(float(_ce), disclaimer_start)
                _wds = str(_txt).split()
                if not _wds or _ce - _cs <= 0.15:
                    continue
                for _i in range(0, len(_wds), 7):
                    _chunk = _wds[_i:_i + 7]
                    _t   = _cs + (_ce - _cs) * (_i / len(_wds))
                    _end = _cs + (_ce - _cs) * (min(_i + 7, len(_wds)) / len(_wds))
                    if _end - _t > 0.15:
                        layers.append(il(frame_caption_anim(" ".join(_chunk), accent),
                                         _t, _end - _t))
                        _n += 1
            print(f"[Captions] {_n} chunks burned in (Roman display text, segment-timed)")
        elif marks:
            _deva_skipped = 0
            for _off, _sdur, _txt in marks:
                if _off >= disclaimer_start:
                    break
                # PIL cannot shape Devanagari — a chunk we can't draw is better
                # skipped than burned in as tofu boxes.
                if any('ऀ' <= _c <= 'ॿ' for _c in _txt):
                    _deva_skipped += 1
                    continue
                _wds = _txt.split()
                if not _wds:
                    continue
                for _i in range(0, len(_wds), 7):
                    _chunk = _wds[_i:_i + 7]
                    _t   = _off + _sdur * (_i / len(_wds))
                    _end = min(_off + _sdur * (min(_i + 7, len(_wds)) / len(_wds)),
                               disclaimer_start)
                    if _end - _t > 0.15:
                        layers.append(il(frame_caption_anim(" ".join(_chunk), accent),
                                         _t, _end - _t))
                        _n += 1
            print(f"[Captions] {_n} chunks burned in (real TTS sentence timings)"
                  + (f"; {_deva_skipped} Devanagari chunks SKIPPED (undrawable)" if _deva_skipped else ""))
        else:
            import re as _re
            _narr  = anim_meta.get("narration", "")
            _sents = [s.strip() for s in _re.split(r'(?<=[.!?])\s+', _narr) if s.strip()]
            _chunks = []
            for _s in _sents:
                _wds = _s.split()
                for _i in range(0, len(_wds), 7):
                    _chunks.append(" ".join(_wds[_i:_i + 7]))
            _total = sum(len(c.split()) for c in _chunks) or 1
            _t = 0.0
            for _c in _chunks:
                _d   = duration * len(_c.split()) / _total
                _end = min(_t + _d, disclaimer_start)
                if _end - _t > 0.15:
                    layers.append(il(frame_caption_anim(_c, accent), _t, _end - _t))
                    _n += 1
                _t += _d
                if _t >= disclaimer_start:
                    break
            print(f"[Captions] {_n} chunks burned in (word-share fallback)")
    except Exception as _ce:
        print(f"[Captions] skipped: {_ce}")

    # No fullscreen title card, and (2026-07-18) no top mini-label either: the
    # 36px title text sat in the phone notch/cutoff zone and was unreadable
    # clutter on every screenshot in the visual QA. The card question IS the
    # on-screen title.

    # Comment prompt, not a follow beg: engagement in the first hour is the
    # heaviest expansion signal. cta_text is passed in by the orchestration
    # (single-fact reels ask a YES/NO "did you know?", which gives the viewer a
    # one-word comment action); the format defaults below are the fallback.
    if not cta_text:
        cta_text = ("Comment your picks: 1 or 2?" if quiz_format == "wyr"
                    else "Comment your score: 0, 1, 2 or 3?")
    # The bar hands off to the outro card (cta_end = outro start): showing the
    # bar AND the card AND a caption all asking for a comment at once is spam.
    _cta_stop = min(disclaimer_start, cta_end) if cta_end else disclaimer_start
    if cta_start < _cta_stop:
        layers.append(il(frame_cta_animated(cta_text, accent), cta_start, _cta_stop - cta_start))

    # No disclaimer bar: a 2.2s static English strip over the final seconds is
    # retention poison on Shorts (the loop lands there on every rewatch) and the
    # disclaimer already lives in the description. disclaimer_start still caps
    # the captions/CTA above, so the video ends clean on the outro card.

    # No fullscreen end card: it blanked the reveal for the last 1.5s, broke
    # the loop-back-to-start illusion, and told viewers "it's over — swipe".

    main_composite = (
        CompositeVideoClip(layers, size=(W, H))
        .set_audio(audio)
        .set_duration(duration)
    )

    # Use main_composite directly - no concatenation needed
    final = main_composite

    music_dir = Path("music")
    if music_dir.exists():
        tracks = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.MP3"))
        if tracks:
            import random as _rnd, math
            music_path = str(_rnd.choice(tracks))
            try:
                from moviepy.editor import AudioFileClip as AFC, CompositeAudioClip, concatenate_audioclips
                music = AFC(music_path)
                if music.duration < duration:
                    loops = math.ceil(duration / music.duration)
                    music = concatenate_audioclips([music] * loops)
                music = music.subclip(0, duration).volumex(0.08)
                final = final.set_audio(CompositeAudioClip([final.audio, music]))
                print(f"[Music] Mixed: {Path(music_path).name}")
            except Exception as e:
                print(f"[Music] Mix failed: {e}")

    final.write_videofile(
        out_path, fps=FPS, codec="libx264",
        audio_codec="aac", preset="ultrafast", threads=2, logger=None,
    )
    from shared import _loudnorm_in_place
    _loudnorm_in_place(out_path)
    print("[Video] Assembled")


# ── Thumbnail ──────────────────────────────────────────────────────────────────
def generate_thumbnail(title: str, accent: tuple, chart_path: str) -> str:
    TW, TH = 1280, 720
    HEADER  = 200   # solid dark header height — title goes here, chart starts below
    FOOTER  = 72    # branding bar height
    CHART_H = TH - HEADER - FOOTER  # 448px for chart content

    # 1. Extract chart frame (75% through = nearly complete animation)
    chart_img = Image.new("RGB", (TW, CHART_H), (12, 14, 28))
    try:
        vc    = VideoFileClip(chart_path)
        frame = vc.get_frame(vc.duration * 0.80)
        vc.close()
        # Crop frame to chart area only (remove any title card overlay that might be present)
        raw = Image.fromarray(frame).resize((TW, TH))
        # Take only the chart zone (below where title card was)
        chart_zone = raw.crop((0, int(TH * 0.26), TW, TH - int(TH * 0.08)))
        chart_img  = chart_zone.resize((TW, CHART_H), Image.LANCZOS)
    except Exception as e:
        print(f"[Thumb] Frame error: {e}")

    # 2. Build full thumbnail canvas
    img  = Image.new("RGB", (TW, TH), (12, 14, 28))

    # Header: solid dark background
    header_bg = Image.new("RGB", (TW, HEADER), (8, 10, 20))
    img.paste(header_bg, (0, 0))

    # Chart zone
    img.paste(chart_img, (0, HEADER))

    # Subtle gradient over chart zone for depth
    ov = Image.new("RGBA", (TW, CHART_H), (0, 0, 0, 0))
    for i in range(CHART_H):
        alpha = int(15 + (i / CHART_H) * 40)
        ImageDraw.Draw(ov).line([(0, i), (TW, i)], fill=(0, 0, 0, alpha))
    chart_layer = Image.alpha_composite(chart_img.convert("RGBA"), ov).convert("RGB")
    img.paste(chart_layer, (0, HEADER))

    draw = ImageDraw.Draw(img)

    # Left accent bar — brand consistency — full height minus footer
    draw.rectangle([(0, 0), (10, TH - FOOTER)], fill=(*accent,))

    # Title text centred vertically in header
    font  = load_font(52)
    lines = wrap_text(title, font, TW - 160)
    lh    = 64
    total = len(lines) * lh
    ty    = (HEADER - total) // 2

    y = max(10, ty)
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        x  = (TW - (bb[2] - bb[0])) // 2
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += lh

    # Thin separator line between header and chart
    draw.rectangle([(10, HEADER - 2), (TW, HEADER)], fill=(*accent,))

    # Branding footer bar
    draw.rectangle([(0, TH - FOOTER), (TW, TH)], fill=(*accent,))
    cfont = load_font(36)
    ctxt  = "  Can you get 3/3?"
    cbb   = draw.textbbox((0, 0), ctxt, font=cfont)
    draw.text(
        ((TW - (cbb[2] - cbb[0])) // 2, TH - FOOTER + (FOOTER - (cbb[3] - cbb[1])) // 2),
        ctxt, font=cfont, fill=(255, 255, 255),
    )

    fd, out = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(out, "PNG")
    return out


# ── Upload ────────────────────────────────────────────────────────────────────
def _build_creds(data) -> Credentials:
    if isinstance(data, str):
        data = json.loads(data)
    c = Credentials.from_authorized_user_info(data)
    if c.expired and c.refresh_token:
        try:
            c.refresh(Request())
        except Exception as e:
            raise RuntimeError(
                f"OAuth token refresh failed: {e}\n"
                "Re-run auth_setup.py locally and update CHANNEL1_CONFIG secret."
            )
    return c


def _upload_with_retry(request, max_attempts: int = 3) -> dict:
    import time
    for attempt in range(max_attempts):
        try:
            resp = None
            while resp is None:
                _, resp = request.next_chunk()
            return resp
        except Exception as e:
            err_str = str(e)
            if attempt < max_attempts - 1 and any(
                code in err_str for code in ["500", "503", "502", "rateLimitExceeded"]
            ):
                wait = 2 ** (attempt + 1)
                print(f"[YouTube] Upload error (attempt {attempt+1}): {e} — retrying in {wait}s")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Upload failed after all retry attempts")


def upload_to_youtube(
    video_path: str,
    thumb_path: str,
    meta: dict,
    creds_data,
    target_channel_id: str,
    concept: str = "",
) -> str:
    creds = _build_creds(creds_data)
    yt    = build("youtube", "v3", credentials=creds)

    try:
        ch_resp = yt.channels().list(part="snippet", mine=True).execute()
        active  = ch_resp.get("items", [])
        if active:
            active_id    = active[0]["id"]
            active_title = active[0]["snippet"]["title"]
            print(f"[YouTube] Active  : {active_title} ({active_id})")
            print(f"[YouTube] Target  : {target_channel_id}")
            if target_channel_id and active_id != target_channel_id:
                raise RuntimeError(
                    f"CHANNEL MISMATCH — would upload to '{active_title}' but target is "
                    f"{target_channel_id}. Re-run auth_setup.py on the correct channel."
                )
            print("[YouTube] ✓ Channel confirmed")
    except RuntimeError:
        raise
    except Exception as e:
        print(f"[YouTube] Channel check skipped: {e}")

    _narr = meta.get("narration", "") or meta["title"]
    hook_teaser = (_narr.split(".")[0] or meta["title"])[:120].rstrip(".,!?") + "..."
    merged_tags = list(dict.fromkeys(meta.get("tags", []) + _CORE_TAGS))[:30]
    affiliate_block = build_affiliate_block(meta.get("concept", ""))
    affiliate_part  = f"{affiliate_block}\n\n" if affiliate_block else ""

    # Devanagari block: first sentence of the spoken-Hindi narration (this
    # video's actual hook) when available, plus a fixed Hindi channel line.
    deva_narr = (meta.get("narration_devanagari") or "").strip()
    deva_hook = ""
    if deva_narr:
        deva_hook = re.split(r"(?<=[।?!.])\s", deva_narr, maxsplit=1)[0][:140].strip()
    deva_block = (
        (f"{deva_hook}\n" if deva_hook else "")
        + "रोज़ नए अजब-गजब तथ्य और सवाल — हिंदी में! जवाब comment में लिखो।\n\n"
    )

    full_description = (
        f"{hook_teaser}\n\n"
        f"{deva_block}"
        f"{meta['description']}\n\n"
        f"{affiliate_part}"
        f"{_HASHTAGS}\n\n"
        f"(!) {DISCLAIMER}"
    )

    body = {
        "snippet": {
            "title":                meta["title"],
            "description":          full_description,
            "tags":                 merged_tags,
            "categoryId":           "27",
            # Audience signal: titles/descriptions are Roman-Hinglish (hi-Latn),
            # the narration is Hindi. "en"/"en-US" told YouTube this was US-English
            # content — the exact wrong audience for this channel.
            "defaultLanguage":      "hi-Latn",
            "defaultAudioLanguage": "hi",
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids":             False,
            # AI disclosure is set via YouTube Studio toggle — not via API insert body
        },
    }

    media   = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1 << 20)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp    = _upload_with_retry(request)

    vid_id = resp["id"]
    print(f"[YouTube] ✓ Live → https://youtube.com/shorts/{vid_id}")
    print(f"[YouTube] ℹ️  Studio reminder: Do NOT enable 'Altered/synthetic content' on this video.")
    print(f"[YouTube]    This flag suppresses Shorts reach. Leave it OFF.")

    if thumb_path and Path(thumb_path).exists():
        try:
            yt.thumbnails().set(
                videoId=vid_id,
                media_body=MediaFileUpload(thumb_path, mimetype="image/png"),
            ).execute()
            print("[YouTube] OK Thumbnail set")
        except Exception as e:
            print(f"[YouTube] Thumbnail skipped: {e}")

    _post_engagement_comment(yt, vid_id, meta["title"])
    _post_pinned_comment(yt, vid_id, meta)
    _post_affiliate_comment(yt, vid_id, meta.get("concept", ""))

    playlist_title = CONCEPT_PLAYLISTS.get(concept, DEFAULT_PLAYLIST)
    pid = _get_or_create_playlist(yt, playlist_title, "playlist_map.json")
    if pid:
        _add_to_playlist(yt, vid_id, pid)

    return vid_id


# ── Main ──────────────────────────────────────────────────────────────────────
async def run(channel_config_json: str) -> None:
    cfg        = json.loads(channel_config_json)
    creds_data = cfg["credentials"]
    accent     = tuple(cfg.get("accent", list(DEFAULT_ACCENT)))
    channel_id = (
        creds_data.get("channel_id", "")
        if isinstance(creds_data, dict)
        else ""
    )

    rng       = random.Random(daily_seed(channel_id))
    # Refresh the stats snapshot BEFORE picking a topic so today's pick learns
    # from yesterday's results. Never fatal — posting beats measuring.
    try:
        from performance import refresh_performance
        _pc = _build_creds(creds_data)
        refresh_performance(
            build("youtube", "v3", credentials=_pc),
            build("youtubeAnalytics", "v2", credentials=_pc),
        )
    except Exception as _pe:
        print(f"[Perf] Refresh skipped: {_pe}")
    # A typo in the workflow_dispatch topic input used to reach ANIMATIONS[key]
    # unguarded — KeyError, failed run, auto-filed issue. Fall back to the
    # rotation instead of dying.
    anim_key = os.environ.get("TOPIC_OVERRIDE", "").strip()
    if anim_key and anim_key not in ANIMATIONS:
        print(f"[Topic] TOPIC_OVERRIDE='{anim_key}' is not a known quiz — using the rotation")
        anim_key = ""
    anim_key = anim_key or pick_animation_type(channel_id, rng)
    anim_meta = copy.deepcopy(ANIMATIONS[anim_key])  # deep copy — tags list must not share reference
    renderer  = RENDERERS[anim_key]
    gemini_key = cfg.get("gemini_api_key", os.environ.get("GEMINI_API_KEY", ""))
    # Dynamic content slot (safe LLM use: subjective WYR only, never facts)
    _dyn = None
    try:
        from charts import hydrate_dynamic
        _dyn = hydrate_dynamic(anim_key, gemini_key)
        if _dyn:
            anim_meta.update(_dyn["meta"])
            renderer = _dyn["renderer"]
    except Exception as _de:
        print(f"[Dynamic] hydration skipped: {_de}")
    if gemini_key:
        _preflight_gemini(gemini_key)

    today = datetime.date.today().isoformat()
    print(f"\n{'='*58}")
    print(f"  Animated: {anim_key}")
    print(f"  Channel : {channel_id}")
    print(f"  Date    : {today}")
    print(f"{'='*58}\n")

    # Step 0: Compute all chart numbers from AU_FINANCE constants, then
    # call Gemini to write a unique narration/title using those exact figures.
    # This guarantees chart and voiceover always match — no hardcoded numbers.
    numbers = compute_anim_numbers(anim_key)
    if numbers and gemini_key:
        script = generate_anim_script(anim_key, numbers, anim_meta, gemini_key)
        anim_meta["title"]       = script["title"]
        anim_meta["narration"]   = script["narration"]
        anim_meta["description"] = script["description"]
    else:
        print("[Script] Skipping Gemini (no key or no numbers) — using fallback narration")

    temp_files: list = []

    try:
        # 1a. Build the quiz segments and Hinglish-localise them (+ the title)
        # BEFORE the voiceover, so the spoken narration is Devanagari-Hinglish and
        # the sentence marks line up with it (keeps segment_starts "real TTS").
        _quiz = _segs = None
        try:
            from charts import QUIZZES, build_segments
            _quiz = (_dyn.get("quiz") if _dyn else None) or \
                    next((q for q in QUIZZES if q["key"] == anim_key), None)
        except Exception as _qe:
            print(f"[Quiz] lookup failed: {_qe}")
        if _quiz:
            _segs = build_segments(_quiz)
            # Narration is PRE-BAKED Devanagari-Hinglish carried on the quiz
            # (quiz["voice"] = one string per segment, same order as build_segments).
            # This removes the live-Gemini dependency that silently shipped English
            # when the deployed key was quota-dead. The on-screen cards stay Roman
            # (set upstream in _india_quizzes); only the SPOKEN text is Devanagari.
            _voice = _quiz.get("voice") or []
            if len(_voice) == len(_segs):
                _segs = [(k, qi, _voice[i]) for i, (k, qi, _t) in enumerate(_segs)]
                print(f"[Hinglish] pre-baked Devanagari narration ({len(_segs)} segments)")
            elif gemini_key:
                _segs = localize_segments_hinglish(_segs, gemini_key)
                print("[Hinglish] no pre-baked voice — fell back to live Gemini localisation")
            else:
                print("[Hinglish] WARNING: no pre-baked voice and no Gemini key — narration will be ENGLISH")
            narration_txt = " ".join(t for _k, _q, t in _segs)
            # Carry the Devanagari narration to upload_to_youtube so the
            # description gets a native-script block (language/geo signal +
            # Hindi search). Guarded: if localisation fell back to English
            # there is no Devanagari to ship.
            if re.search(r"[ऀ-ॿ]", narration_txt):
                anim_meta["narration_devanagari"] = narration_txt
        else:
            narration_txt = anim_meta["narration"]

        # 1b. Voiceover FIRST — get exact audio duration; chart is rendered to match.
        fd, audio_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        temp_files.append(audio_path)
        audio_duration, marks = await generate_voiceover(narration_txt, audio_path)

        if audio_duration < 1.0:
            raise RuntimeError("Voiceover duration too short — edge-tts may have failed silently")

        # Real segment boundaries from the TTS marks drive the reveal, beeps and
        # captions. The gaps are spliced in first so the whole render matches the
        # longer, gapped audio.
        seg_starts = None
        if _quiz and _segs:
            try:
                from charts import segment_starts, insert_countdown_gaps
                audio_duration, marks = insert_countdown_gaps(
                    audio_path, _segs, marks, audio_duration)
                seg_starts, _real = segment_starts(_segs, audio_duration, marks)
                print(f"[Sync] segment timings: {'real TTS' if _real else 'word-share fallback'}")
            except Exception as _te:
                print(f"[Sync] segment timing skipped: {_te}")

        try:
            from charts import mix_quiz_sfx
            mix_quiz_sfx(audio_path, anim_key, audio_duration, seg_starts=seg_starts)
        except Exception as _se:
            print(f"[SFX] skipped: {_se}")
        print(f"[1/5] Voiceover: {audio_duration:.1f}s")

        # Roman caption track. The spoken narration is Devanagari, which the
        # caption renderer cannot draw (PIL has no Indic shaping -> tofu), so
        # the burned-in captions display the quiz's ROMAN-Hinglish text, timed
        # by the same real segment boundaries the reveal/beeps use.
        _captions = None
        _outro_start = None
        if _quiz and _segs and seg_starts:
            _cap_txt = []
            for _si, (_kind, _qi, _t) in enumerate(_segs):
                if _kind == "intro":
                    _cap_txt.append(_quiz.get("hook", ""))
                elif _kind == "ask":
                    _cap_txt.append(_quiz["questions"][_qi].get("q", ""))
                elif _kind == "reveal":
                    _qq = _quiz["questions"][_qi]
                    _cap_txt.append(f"Sahi jawab: {_qq['options'][_qq['answer']]}! "
                                    f"{_qq.get('fact', '')}")
                else:
                    # NO outro caption: the outro card says the same words, and
                    # three simultaneous "comment!" prompts (card + CTA bar +
                    # caption) read as spam. The card alone owns the outro.
                    _cap_txt.append("")
                    _outro_start = seg_starts[_si]
            _ends = list(seg_starts[1:]) + [audio_duration]
            _captions = [(_cap_txt[i], seg_starts[i], _ends[i])
                         for i in range(len(_segs)) if _cap_txt[i].strip()]

        # 2. Photo background (Pexels). Dormant without a key — falls back to
        # the dark canvas, so this never blocks a post.
        bg_path = None
        try:
            from backgrounds import fetch as fetch_bg
            fd, bg_path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            temp_files.append(bg_path)
            _qs  = (_quiz or {}).get("questions", []) or [{}]
            _q0  = _qs[0]
            # One photo sits behind all three questions, so every option of every
            # question is a potential spoiler — bar the lot from the search.
            _opts = [o for _q in _qs for o in (_q.get("options") or [])]
            # Prefer the curated per-fact image_query — the query_for() heuristic
            # mangles fact questions ("...Leaning Tower of Pisa?" -> "Leaning
            # Indian" -> a random street photo). image_query is spoiler-free.
            bg_path = fetch_bg(_q0.get("q", anim_meta["title"]), _opts,
                               (_quiz or {}).get("concept", ""), bg_path,
                               fmt=(_quiz or {}).get("format", "trivia"),
                               query_override=_q0.get("image_query", ""))
        except Exception as _be:
            print(f"[BG] skipped: {_be}")
            bg_path = None

        # 3. Render chart animation at exactly audio_duration seconds
        fd, chart_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        temp_files.append(chart_path)
        renderer(chart_path, accent, audio_duration, seg_starts=seg_starts, bg_image=bg_path)
        print(f"[2/5] Chart animation: done")

        # 3. Thumbnail — uses Gemini-generated title
        thumb_path = generate_thumbnail(anim_meta["title"], accent, chart_path)
        temp_files.append(thumb_path)
        print("[3/5] Thumbnail: done")

        # 4. Assemble video
        fd, video_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        temp_files.append(video_path)
        _one_fact = bool(_quiz) and len(_quiz.get("questions") or []) == 1
        build_video(chart_path, audio_path, audio_duration, anim_meta, video_path, accent,
                    marks=marks, bg_image=bg_path,
                    quiz_format=(_quiz or {}).get("format", "trivia"),
                    captions=_captions,
                    cta_text="Pata tha? Comment: YES ya NO!" if _one_fact else None,
                    cta_end=_outro_start)
        print("[4/5] Video: assembled")

        # Media QA: silence/duration/audio levels. Warn, never block.
        try:
            from quality_scorer import score_media_artifacts
            _media = score_media_artifacts(Path(video_path))
            for _k, _v in _media.items():
                if _k.endswith("_note"):
                    _ok = _media.get(_k[:-5] + "_ok")
                    _tag = "OK" if _ok else ("WARN" if _ok is False else "info")
                    print(f"[Media QA {_tag}] {_v}")
        except Exception as _me:
            print(f"[Media QA] skipped: {str(_me)[:80]}")

        # QA gate before upload
        _qr = score_pipeline_output(anim_meta, "animated")
        print(f"[QA] Score {_qr.total:.1f}/10 — {_qr.summary()} | viral hook {_qr.viral_hook_score:.0f}/10")
        for _issue in _qr.issues:    print(f"[QA] FAIL {_issue}")
        for _pos   in _qr.positives: print(f"[QA] PASS {_pos}")
        # The video is already fully rendered here — discarding it over a script
        # score wastes the render AND the posting day. Warn-and-post above a
        # hard floor. The floor is 4.0 (not quizora's 5.5): the scorer's hook/
        # title heuristics are keyed to ENGLISH patterns and have not been
        # validated on Hinglish text — an abort on an unvalidated scorer is a
        # silently lost posting slot. Revisit once ~20 Hinglish reels have
        # scored (first 5 ran 7.8-8.25, so the floor should rarely matter).
        if _qr.total < 4.0:
            raise SystemExit(f"[QA] Score {_qr.total:.1f} below hard floor (5.5) — aborting. Weakest: {_qr.weakest_dimension}")
        if _qr.total < 6.5:
            print(f"[QA] WARN: {_qr.total:.1f} below gate (6.5) — posting anyway (render is sunk, missed day costs more). Weakest: {_qr.weakest_dimension}")

        # ── Language guard (Hinglish channel). A quota-dead Gemini key once
        # silently shipped an all-ENGLISH reel on a green run; fail LOUD instead.
        # Rule 1: spoken narration MUST contain Devanagari (catches the English
        #         fallback exactly). Rule 2: on-screen card text must NOT contain
        #         Devanagari — the CI runner has no Deva font, so it renders as
        #         tofu boxes (invisible when eyeballed on Windows, which has one).
        def _has_deva(s):
            return any('ऀ' <= c <= 'ॿ' for c in (s or ""))
        if (anim_key or "").startswith("in_"):
            if not _has_deva(narration_txt):
                raise SystemExit("[Lang] ABORT: narration contains NO Devanagari — an "
                                 "English fallback was about to ship. Check the fact's "
                                 "pre-baked hi.voice (or the Gemini key).")
            _cards = [anim_meta.get("title", "")]
            if _quiz:
                _cards += [_quiz.get("hook", ""), _quiz.get("outro", "")]
                for _q in _quiz.get("questions", []):
                    _cards += [_q.get("q", ""), _q.get("fact", "")] + list(_q.get("options") or [])
            if _captions:
                _cards += [t for (t, _s, _e) in _captions]
            _tofu = [s for s in _cards if _has_deva(s)]
            if _tofu:
                raise SystemExit(f"[Lang] ABORT: card text has Devanagari (tofu in CI): {_tofu[:2]}")
            print("[Lang] OK — Devanagari narration + Roman/ASCII cards verified")

        # 5. Upload
        vid_id = upload_to_youtube(video_path, thumb_path, anim_meta, creds_data, channel_id,
                                   concept=anim_key)
        print(f"[5/5] Done -> https://youtube.com/shorts/{vid_id}\n")

        log_anim_type(anim_key, channel_id, quality_score=_qr.total)

        # Also append to the cross-pipeline topic ledger so concept_performance
        # in intelligence_report.json sees animated videos. Previously only
        # log_anim_type fired here, causing ~half of live videos to be invisible
        # to the analytics/learning loop.
        try:
            _hook_for_ledger = (anim_meta.get("narration", "").split(".")[0] or
                                anim_meta.get("title", ""))[:140]
            _add_to_topic_ledger(
                title=anim_meta["title"],
                hook=_hook_for_ledger,
                channel_id=channel_id,
                source="animated",
                concept=anim_key,
                quality_score=_qr.total,
                video_id=vid_id,
                forced=(os.environ.get("FORCE_POST") == "1"),
            )
        except Exception as _le:
            print(f"[Ledger] WARN animated topic_ledger append failed: {_le}")

        print("-" * 58)
        print("  [OK] POSTED - Manual Studio tasks:")
        print(f"  [ ] End screen: add 'Playlist' card")
        print(f"  [ ] Cards: at 10s mark, link to main playlist")
        print(f"  [ ] Add video to your Shorts playlist")
        print(f"  [ ] Do NOT toggle 'Altered/synthetic content' - leave OFF")
        print("-" * 58 + "\n")

    finally:
        for p in temp_files:
            try:
                if p and Path(p).exists():
                    os.remove(p)
            except OSError:
                pass


if __name__ == "__main__":
    config = os.environ.get("CHANNEL_CONFIG")
    if not config:
        raise SystemExit("ERROR: CHANNEL_CONFIG environment variable not set.")
    # Hard daily cap for EVERY trigger: >3/day is our own spam line, and an
    # unguarded workflow_dispatch (double cron-job.org fire, manual run) would
    # sail past it. Deliberate extras must set FORCE_POST=1.
    from shared import already_posted_today
    if os.environ.get("FORCE_POST") != "1" and already_posted_today("animated", slot_cap=4):
        print("[Guard] Daily cap (4) reached — exiting cleanly. "
              "Set FORCE_POST=1 for a deliberate extra post.")
        raise SystemExit(0)
    # Backup scheduled runs set SKIP_IF_POSTED_TODAY=1: they only exist to
    # retry a failed slot. 3 slots/day — the expected post count by this hour
    # decides whether the slot was filled (slot 1 ≈ 13:00, 2 ≈ 18:00, 3 ≈ 23:00 UTC).
    # GitHub delays schedule events by hours under load (8h seen 2026-07-12,
    # which slid the 23:30 backup past UTC midnight and double-posted): judge
    # the slot by its SCHEDULED time (TRIGGER_CRON = github.event.schedule),
    # and drop any backup whose scheduled day is no longer today.
    if os.environ.get("SKIP_IF_POSTED_TODAY") == "1":
        now = datetime.datetime.now(datetime.timezone.utc)
        h = now.hour
        cron = os.environ.get("TRIGGER_CRON", "").split()
        if len(cron) >= 2 and cron[0].isdigit() and cron[1].isdigit():
            sched = now.replace(hour=int(cron[1]), minute=int(cron[0]),
                                second=0, microsecond=0)
            if sched > now:
                sched -= datetime.timedelta(days=1)
            if sched.date() != now.date():
                print("[Guard] Backup run delayed past UTC midnight — stale, exiting cleanly.")
                raise SystemExit(0)
            h = sched.hour
        expected = 1 if h < 8 else 2 if h < 13 else 3 if h < 17 else 4
        if already_posted_today("animated", slot_cap=expected):
            print(f"[Guard] Slot {expected} already filled today — backup run exiting cleanly.")
            raise SystemExit(0)
    asyncio.run(run(config))
