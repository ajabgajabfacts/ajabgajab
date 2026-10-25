"""fb.py — cross-post a katha Short to the Ajab Gajab Stories Facebook Page as a Reel.

Built 2026-10-23, same Graph API Reels flow as quizora/fb.py (start -> upload
-> publish) with a never-expiring Page token:
  CI      env FB_PAGE_TOKEN (secret FB_PAGE_TOKEN_AJAB) = the JSON in fb_page_token.txt
  local   ajabgajab/fb_page_token.txt (git-ignored)

  - Never raises: YouTube is the product, so a Facebook failure only prints.
  - Only FB_SLOTS go: slot 1 (12:05 IST, the rotating regional languages that made the
    Mysore Palace record) and slot 3 (20:35 IST, Telugu, India's evening peak).
  - At most MAX_PER_DAY per UTC day, counted from the Page, so re-runs can't double-post.
    Raised 2 -> 3 on 2026-10-25 (new Page, 0 followers: frequency helps it get found).
  - While katha/fb_backfill.json still has queued top Shorts, the slot cross-post stands
    down so the cap goes to the proven Shorts first (Mysore Palace kn etc.).
  - English (Strange But True) has no Page here and never posts.
  - The caption carries the Wikimedia credits: CC BY-SA requires them wherever the images go.
"""
import json, os, time, datetime
from pathlib import Path
import requests

G = "https://graph.facebook.com/v23.0"
MAX_PER_DAY = 3
FB_SLOTS = {1, 3}


def _cfg():
    raw = os.environ.get("FB_PAGE_TOKEN")
    if not raw:
        f = Path(__file__).resolve().parent.parent / "fb_page_token.txt"
        raw = f.read_text(encoding="utf-8") if f.exists() else ""
    return json.loads(raw) if raw else None


def posted_today(cfg):
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    r = requests.get(f"{G}/{cfg['page_id']}/video_reels",
                     params={"fields": "created_time", "limit": 25, "access_token": cfg["page_token"]}, timeout=30)
    r.raise_for_status()
    return sum(1 for v in r.json().get("data", []) if v.get("created_time", "").startswith(today))


def post_reel(video_path, caption, slot=None, lang=None, backfill=False):
    try:
        if os.environ.get("FB_DISABLE") or lang == "en":
            return None
        if not backfill:
            if slot not in FB_SLOTS and not os.environ.get("FB_FORCE"):
                print(f"[FB] slot {slot} is not a Facebook slot - skipped"); return None
            import fb_backfill                    # the proven top Shorts get the daily cap first
            if fb_backfill.pending():
                print(f"[FB] {len(fb_backfill.pending())} top Shorts still queued for Facebook - new Short skipped"); return None
        cfg = _cfg()
        if not cfg:
            print("[FB] no Page token - skipped"); return None
        n = posted_today(cfg)
        if n >= MAX_PER_DAY:
            print(f"[FB] {n} Reels already today (cap {MAX_PER_DAY}) - skipped"); return None
        pid, tok = cfg["page_id"], cfg["page_token"]
        r = requests.post(f"{G}/{pid}/video_reels", data={"upload_phase": "start", "access_token": tok}, timeout=30)
        r.raise_for_status()
        vid, url = r.json()["video_id"], r.json()["upload_url"]
        with open(video_path, "rb") as fh:
            requests.post(url, data=fh, timeout=300, headers={
                "Authorization": f"OAuth {tok}", "offset": "0",
                "file_size": str(os.path.getsize(video_path))}).raise_for_status()
        requests.post(f"{G}/{pid}/video_reels", timeout=60, data={
            "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
            "description": caption[:2200], "access_token": tok}).raise_for_status()
        st = None
        for _ in range(20):
            st = (requests.get(f"{G}/{vid}", params={"fields": "status", "access_token": tok},
                               timeout=30).json().get("status") or {}).get("video_status")
            if st in ("ready", "error"):
                break
            time.sleep(6)
        print(f"[FB] Reel {vid} status={st}")
        return vid
    except Exception as e:
        print(f"[FB] cross-post failed: {e} {getattr(getattr(e, 'response', None), 'text', '')[:300]}")
        return None
