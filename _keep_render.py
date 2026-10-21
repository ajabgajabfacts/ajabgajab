# -*- coding: utf-8 -*-
"""Local render that KEEPS the mp4 (test_local.py's goes to a tempfile that the
pipeline deletes). Scratch harness — not part of the pipeline.

Same shape as level3challenge/_keep_render.py. It exists because this repo's
own rule is that nothing ships unlooked, and test_local.py leaves nothing to
look at.

    python _keep_render.py out.mp4          # rotation picks the topic
    python _keep_render.py out.mp4 <key>    # force one topic key
"""
import os, sys, json, asyncio, shutil
from pathlib import Path

DEST = Path(sys.argv[1] if len(sys.argv) > 1 else "keep.mp4").resolve()

if not os.environ.get("GEMINI_API_KEY"):
    _env = Path(__file__).parent / ".env"
    if _env.exists():
        for line in _env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY"):
                os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip().strip("'\"")
_pk = Path(__file__).parent / "pexels_api.txt"
if _pk.exists() and not os.environ.get("PEXELS_API_KEY"):
    os.environ["PEXELS_API_KEY"] = _pk.read_text(encoding="utf-8").strip()

import pipeline_animated as pa


def _grab(video_path, *a, **k):
    shutil.copy(video_path, DEST)
    print(f"[KEEP] {DEST}")
    return "DRYRUN0000"


pa.upload_to_youtube = _grab
pa.log_anim_type = lambda *a, **k: None
if hasattr(pa, "_add_to_topic_ledger"):
    pa._add_to_topic_ledger = lambda *a, **k: None

if len(sys.argv) > 2:
    os.environ["FORCE_TOPIC"] = sys.argv[2]

cfg = json.dumps({"credentials": {"channel_id": "DRYRUN"},
                  "gemini_api_key": os.environ.get("GEMINI_API_KEY", "")})
asyncio.run(pa.run(cfg))
