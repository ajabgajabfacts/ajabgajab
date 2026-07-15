# -*- coding: utf-8 -*-
"""Local dry run: full pipeline (Gemini narration -> TTS -> chart render ->
video assembly -> QA score) with the upload and comments stubbed out.
Usage: python test_local.py [topic_key]
Reads GEMINI_API_KEY from ../week_test/files/.env if not set (borrowed for
local testing only — production uses this repo's own secrets)."""
import os, sys, json, asyncio
from pathlib import Path

if not os.environ.get("GEMINI_API_KEY"):
    _env = Path(r"C:\Users\parit\Desktop\YT_project\week_test\files\.env")
    if _env.exists():
        for line in _env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY"):
                os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip().strip("'\"")

import pipeline_animated as pa

pa.upload_to_youtube = lambda *a, **k: (print("[DRY] upload skipped"), "DRYRUN0000")[1]
pa.log_anim_type = lambda *a, **k: print("[DRY] anim ledger skipped")
pa._add_to_topic_ledger = lambda *a, **k: print("[DRY] topic ledger skipped")

if len(sys.argv) > 1:
    key = sys.argv[1]
    pa.pick_animation_type = lambda cid, rng: key

cfg = json.dumps({
    "credentials": {"channel_id": "DRYRUN"},
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
})
asyncio.run(pa.run(cfg))
print("\nDRY RUN COMPLETE")
