# -*- coding: utf-8 -*-
"""Shared ledger/audio helpers — extracted from the Money Sorted AU pipeline
so pipeline_animated.py runs standalone in this charts-only repo."""
import json, datetime
from pathlib import Path

TOPIC_LEDGER_PATH  = Path("topic_ledger.json")
LEDGER_MAX_ENTRIES = 400   # ~4 months at 3/day
CURRICULUM_EPOCH   = 1


def load_topic_ledger() -> list:
    try:
        if TOPIC_LEDGER_PATH.exists():
            with open(TOPIC_LEDGER_PATH, encoding="utf-8-sig") as f:
                return json.load(f)
    except Exception as e:
        print(f"[Ledger] Read failed: {e}")
    return []


def save_topic_ledger(ledger: list) -> None:
    try:
        with open(TOPIC_LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(ledger[-LEDGER_MAX_ENTRIES:], f, indent=2)
    except Exception as e:
        print(f"[Ledger] Write failed: {e}")


def add_to_ledger(title: str, hook: str, channel_id: str,
                  source: str = "animated", concept: str = "chart",
                  topic_index: int = None, quality_score: float = None,
                  fmt: str = None, video_id: str = None,
                  forced: bool = False) -> None:
    ledger = load_topic_ledger()
    entry = {
        "date":       datetime.date.today().isoformat(),
        "channel_id": channel_id,
        "title":      title,
        "hook":       hook,
        "source":     source,
        "concept":    concept,
        "curriculum": CURRICULUM_EPOCH,
    }
    if forced:
        # A deliberate extra (FORCE_POST=1) is an EXTRA — it must not eat one of
        # the day's three scheduled slots. already_posted_today skips these, so a
        # hand-run test post cannot cause a later cron slot to be skipped.
        entry["forced"] = True
    if topic_index is not None:
        entry["topic_index"] = topic_index
    if quality_score is not None:
        entry["quality_score"] = round(quality_score, 2)
    if fmt is not None:
        entry["format"] = fmt
    if video_id:
        entry["video_id"] = video_id  # joins ledger to live stats (performance.py)
    ledger.append(entry)
    save_topic_ledger(ledger)
    print(f"[Ledger] Logged: {title[:50]} | concept={concept}")


def already_posted_today(post_type: str = "animated", slot_cap: int = 3) -> bool:
    """True if today's (UTC) post count has hit slot_cap. This channel posts
    3 charts/day — backup runs must retry a missed slot without duplicating
    a filled one, so the guard counts posts rather than checking existence.

    Forced posts (FORCE_POST=1, a hand-run test) are excluded: they are extras on
    top of the day's three, so counting them here would silently cancel a later
    scheduled slot — the run would post 3 videos total instead of 4.
    """
    today = datetime.date.today().isoformat()
    n = sum(1 for e in load_topic_ledger()
            if e.get("date") == today and not e.get("forced"))
    return n >= slot_cap


def _loudnorm_in_place(mp4_path: str) -> None:
    """EBU R128 loudnorm to YouTube's -14 LUFS target, in-place.
    Silently no-ops if ffmpeg is missing or the pass fails."""
    import subprocess, os
    tmp = mp4_path + ".norm.mp4"
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", mp4_path,
             "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
             # -ar 48000 IS LOAD-BEARING. ffmpeg's loudnorm filter upsamples
             # internally to 192 kHz, and with no explicit rate the AAC encoder
             # clamps to its 96 kHz maximum — so every video this pipeline has
             # produced shipped as 96 kHz AAC. It decodes fine and YouTube
             # transcodes it, but Windows' built-in players decode 96 kHz AAC as
             # SILENCE, which makes local review of a render impossible.
             # 48 kHz is YouTube's recommendation and plays everywhere.
             "-ar", "48000",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             tmp],
            capture_output=True, timeout=120,
        )
        if proc.returncode == 0 and os.path.getsize(tmp) > 0:
            os.replace(tmp, mp4_path)
            print("[Loudnorm] normalised to -14 LUFS")
        else:
            print(f"[Loudnorm] skipped (ffmpeg rc={proc.returncode})")
            if os.path.exists(tmp):
                os.remove(tmp)
    except Exception as e:
        print(f"[Loudnorm] skipped ({type(e).__name__}: {str(e)[:60]})")
        import os as _os
        if _os.path.exists(tmp):
            try:
                _os.remove(tmp)
            except OSError:
                pass
