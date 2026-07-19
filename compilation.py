"""Weekly long-form compilation — 30 recent sawaal in one regular video.

Same idea as quizora's compilation.py, adapted for this channel's 1-question
reels with PRE-BAKED Devanagari narration: each reel carries
hi.voice = [hook, ask, reveal, outro], so the compilation narration is a new
Hindi intro + every reel's ask/reveal lines + a new Hindi outro — no live
Gemini, no English fallback risk.

Bookkeeping lives in compilation_ledger.json, NOT topic_ledger.json, so the
daily posted-today guards never see these rows.
"""

import asyncio, datetime, json, os, tempfile
from functools import partial
from pathlib import Path

from PIL import Image, ImageDraw

from charts import (QUIZZES, build_segments, insert_countdown_gaps,
                    mix_quiz_sfx, render_quiz, segment_starts)
from pipeline_animated import (DEFAULT_ACCENT, _build_creds,
                               _upload_with_retry, generate_voiceover, load_font)
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

QUESTIONS_TARGET = 30
MIN_REELS        = 12
LEDGER           = Path(__file__).parent / "compilation_ledger.json"

# Cards stay Roman (CI runner has no Devanagari font); voice is Devanagari.
HOOK_CARD   = "30 sawaal — kitne sahi kar paoge? Score gino!"
# One flowing comma-joined sentence — edge-tts turns every danda/full stop
# into a flat robotic reset, which longer intros expose badly.
INTRO_VOICE = ("तीस सवाल आ रहे हैं, और ज़्यादातर लोग बीस भी सही नहीं कर पाते, "
               "तो score गिनते रहना, और आख़िर में अपना total comment में ज़रूर बताना!")
OUTRO_VOICE = "तीस में से कितने सही हुए? Comment में ज़रूर बताओ!"
TAGS_LINE   = ("#AjabGajabFacts #रोचकतथ्य #अजबगजब #GKQuiz #FactsInHindi "
               "#HindiQuiz #GeneralKnowledge #QuizTime")


def _load_ledger() -> list:
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return []


def _pick_reels() -> list:
    """Posted reels first (newest-first, distinct), padded from the rest of the
    bank; anything in the previous compilation is excluded."""
    try:
        rows = json.loads((Path(__file__).parent / "topic_ledger.json")
                          .read_text(encoding="utf-8"))
    except Exception:
        rows = []
    comp_rows = _load_ledger()
    last_used = set(comp_rows[-1]["concepts"]) if comp_rows else set()
    by_key = {q["key"]: q for q in QUIZZES
              if q.get("format") == "trivia" and len(q.get("voice") or []) == 4}

    picked, seen = [], set()
    for r in reversed(rows):
        k = r.get("concept")
        if k in by_key and k not in seen and k not in last_used:
            picked.append(by_key[k]); seen.add(k)
        if len(picked) >= QUESTIONS_TARGET:
            return picked
    for k, q in by_key.items():
        if k not in seen and k not in last_used:
            picked.append(q); seen.add(k)
        if len(picked) >= QUESTIONS_TARGET:
            break
    return picked


def _mega_quiz(picked: list, n: int) -> dict:
    return {
        "key": "weekly_compilation", "format": "trivia", "concept": "geography",
        "title": f"30 Ajab Gajab Sawaal — Kitne Sahi Kar Paoge? (Mega Quiz #{n})",
        "hook": HOOK_CARD,
        "questions": [q["questions"][0] for q in picked][:QUESTIONS_TARGET],
    }


def _voice_lines(picked: list) -> list:
    """One Devanagari line per segment: intro + (ask, reveal)*N + outro."""
    lines = [INTRO_VOICE]
    for q in picked[:QUESTIONS_TARGET]:
        lines += [q["voice"][1], q["voice"][2]]
    lines.append(OUTRO_VOICE)
    return lines


def _thumbnail(accent: tuple) -> str:
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#12121C")
    d = ImageDraw.Draw(img)
    ax = "#%02X%02X%02X" % tuple(accent)
    d.rectangle([0, H - 26, W, H], fill=ax)
    d.text((W // 2, 200), "30 SAWAAL", font=load_font(140), fill="white", anchor="mm")
    d.text((W // 2, 380), "KITNE SAHI KAR PAOGE?", font=load_font(66), fill=ax, anchor="mm")
    d.text((W // 2, 540), "MEGA GK QUIZ", font=load_font(54), fill="#9CA3AF", anchor="mm")
    fd, p = tempfile.mkstemp(suffix=".png"); os.close(fd)
    img.save(p, "PNG")
    return p


def _chapters(segs, starts) -> str:
    lines, qn = ["0:00 Intro"], 0
    for (kind, qi, _t), t in zip(segs, starts):
        if kind != "ask":
            continue
        qn += 1
        m, s = divmod(int(t), 60)
        lines.append(f"{m}:{s:02d} Sawaal {qn}")
    return "\n".join(lines)


async def main() -> None:
    cfg = json.load(open(Path(__file__).parent / "CHANNEL_Ajab_Gajab_Facts_CONFIG.json")) \
        if not os.environ.get("CHANNEL_CONFIG") else json.loads(os.environ["CHANNEL_CONFIG"])
    creds_data = cfg["credentials"]
    channel_id = creds_data.get("channel_id", "")
    accent = tuple(cfg.get("accent", list(DEFAULT_ACCENT)))

    comp_rows = _load_ledger()
    today = datetime.date.today().isoformat()
    if any(r["date"] == today for r in comp_rows) and os.environ.get("FORCE_POST") != "1":
        print("[Comp] already posted a compilation today — exiting")
        return

    picked = _pick_reels()
    if len(picked) < MIN_REELS:
        raise SystemExit(f"[Comp] only {len(picked)} eligible reels — not enough")
    # Bank padding arrives in file order, which clumps topics (Mega Quiz #1
    # ended on 11 straight cricket questions). Shuffle so topics interleave.
    import random
    random.shuffle(picked)
    quiz = _mega_quiz(picked, len(comp_rows) + 1)
    segs = build_segments(quiz)
    voice = _voice_lines(picked)
    if len(voice) != len(segs):
        raise SystemExit(f"[Comp] voice/segment mismatch: {len(voice)} vs {len(segs)}")
    segs = [(k, qi, voice[i]) for i, (k, qi, _t) in enumerate(segs)]
    narration = " ".join(t for _k, _q, t in segs)
    print(f"[Comp] {len(quiz['questions'])} sawaal, narration segs {len(segs)}")

    temp_files = []
    try:
        fd, audio_path = tempfile.mkstemp(suffix=".mp3"); os.close(fd)
        temp_files.append(audio_path)
        audio_duration, marks = await generate_voiceover(narration, audio_path)
        if audio_duration < 60:
            raise RuntimeError("compilation voiceover suspiciously short")
        audio_duration, marks = insert_countdown_gaps(audio_path, segs, marks,
                                                      audio_duration)
        starts, _real = segment_starts(segs, audio_duration, marks)
        try:
            mix_quiz_sfx(audio_path, quiz["key"], audio_duration,
                         seg_starts=starts, quiz=quiz)
        except Exception as e:
            print(f"[Comp] SFX skipped: {e}")
        print(f"[Comp] narration {audio_duration/60:.1f} min "
              f"({'real TTS' if _real else 'word-share'} timings)")

        bg_path = None
        try:
            from backgrounds import fetch as fetch_bg
            fd, bg_path = tempfile.mkstemp(suffix=".jpg"); os.close(fd)
            temp_files.append(bg_path)
            opts = [o for q in quiz["questions"] for o in q.get("options", [])]
            bg_path = fetch_bg("india knowledge quiz", opts, "geography", bg_path,
                               fmt="trivia")
        except Exception as e:
            print(f"[Comp] BG skipped: {e}")
            bg_path = None

        fd, video_path = tempfile.mkstemp(suffix=".mp4"); os.close(fd)
        temp_files.append(video_path)
        partial(render_quiz, quiz=quiz)(video_path, accent, audio_duration,
                                        seg_starts=starts, bg_image=bg_path)

        fd, final_path = tempfile.mkstemp(suffix=".mp4"); os.close(fd)
        temp_files.append(final_path)
        import subprocess
        # 16:9 canvas with blurred self-fill — long-form is watched on
        # desktop/TV where a bare 9:16 strip reads as repurposed content.
        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-i", audio_path,
                        "-filter_complex",
                        "[0:v]scale=1920:1080,boxblur=24:4[bg];"
                        "[0:v]scale=-2:1080[fg];[bg][fg]overlay=(W-w)/2:0",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", final_path],
                       check=True, capture_output=True)

        thumb_path = _thumbnail(accent)
        temp_files.append(thumb_path)

        description = (
            f"{HOOK_CARD}\n\n"
            "तीस अजब-गजब सवाल — score comment में बताओ! "
            "रोज़ 4 नए facts ke liye subscribe karo.\n\n"
            f"{_chapters(segs, starts)}\n\n{TAGS_LINE}"
        )
        creds = _build_creds(creds_data)
        yt = build("youtube", "v3", credentials=creds)
        active = yt.channels().list(part="snippet", mine=True).execute()["items"]
        if active and channel_id and active[0]["id"] != channel_id:
            raise RuntimeError("CHANNEL MISMATCH — wrong credentials for target channel")
        body = {
            "snippet": {"title": quiz["title"], "description": description,
                         "tags": ["gk quiz hindi", "ajab gajab facts", "hindi quiz",
                                  "general knowledge quiz", "quiz compilation",
                                  "रोचक तथ्य", "अजब गजब"],
                         "categoryId": "27",
                         "defaultLanguage": "hi-Latn", "defaultAudioLanguage": "hi"},
            "status": {"privacyStatus": "public",
                        "selfDeclaredMadeForKids": False, "madeForKids": False},
        }
        media = MediaFileUpload(final_path, mimetype="video/mp4",
                                resumable=True, chunksize=1 << 20)
        resp = _upload_with_retry(yt.videos().insert(part="snippet,status",
                                                     body=body, media_body=media))
        vid_id = resp["id"]
        try:
            yt.thumbnails().set(videoId=vid_id,
                                media_body=MediaFileUpload(thumb_path,
                                                           mimetype="image/png")).execute()
        except Exception as e:
            print(f"[Comp] thumbnail failed: {e}")
        # The shorts comment helper's score text is per-video — the mega quiz
        # posts its own 30-question CTA.
        try:
            n = len(quiz["questions"])
            yt.commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": vid_id, "topLevelComment": {"snippet": {"textOriginal":
                    f"{n} mein se kitne sahi hue? Comment mein batao — "
                    "sabse tricky kaunsa laga?"}}}}).execute()
        except Exception as e:
            print(f"[Comp] comment failed: {e}")

        comp_rows.append({"date": today, "video_id": vid_id,
                          "title": quiz["title"],
                          "concepts": [q["key"] for q in picked]})
        LEDGER.write_text(json.dumps(comp_rows, indent=1), encoding="utf-8")
        print(f"[Comp] LIVE -> https://youtube.com/watch?v={vid_id}")
    finally:
        for p in temp_files:
            try:
                if p and Path(p).exists():
                    os.remove(p)
            except OSError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
