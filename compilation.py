"""Weekly mega-round — a longer play-along Short built from recent sawaal.

Same idea as quizora's compilation.py, adapted for this channel's 1-question
reels with PRE-BAKED Devanagari narration: each reel carries
hi.voice = [hook, ask, reveal, outro], so the compilation narration is a new
Hindi intro + every reel's ask/reveal lines + a new Hindi outro — no live
Gemini, no English fallback risk.

**It must stay UNDER 3 minutes and stay VERTICAL, or it is not a Short.**
The v1 build was 30 sawaal on a 16:9 blurred canvas — an 11:46 LANDSCAPE video
— and got 2 views. See quizora/compilation.py for the full reasoning; the short
version is that the Shorts feed is the only distribution this channel has, so a
long-form landscape upload reaches nobody.

The Hindi voice is noticeably slower than the English one (~23.5 s/sawaal vs
~18.7), hence the lower QUESTIONS_TARGET; _fit_under_shorts_cap() drops sawaal
until the audio actually fits, so the count is a starting point, not a promise.

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

QUESTIONS_TARGET = 6           # ~23.5 s/sawaal on the Hindi voice -> ~2:35
MIN_QUESTIONS    = 4           # below this the video is too thin — abort
MIN_REELS        = 6           # need at least QUESTIONS_TARGET reels to pick from
SHORTS_MAX_S     = 176.0       # 3:00 is the hard Shorts ceiling; leave headroom
LEDGER           = Path(__file__).parent / "compilation_ledger.json"

# Devanagari numerals for the spoken lines; cards stay Roman (CI runner has no
# Devanagari font).
_HI = {4: "चार", 5: "पांच", 6: "छह", 7: "सात", 8: "आठ"}

# Test runs must not reach subscribers: set COMP_PRIVACY=unlisted (or private)
# on a workflow_dispatch to validate a build without publishing it. The Sunday
# cron leaves it unset, so scheduled runs stay public.
PRIVACY = os.environ.get("COMP_PRIVACY", "public")


def _hook_card(n: int) -> str:
    return f"{n} sawaal — kitne sahi kar paoge? Score gino!"


def _intro_voice(n: int) -> str:
    """One flowing comma-joined sentence — edge-tts turns every danda/full stop
    into a flat robotic reset, which longer intros expose badly."""
    return (f"{_HI.get(n, str(n))} सवाल आ रहे हैं, और ज़्यादातर लोग सारे सही नहीं कर पाते, "
            "तो score गिनते रहना, और आख़िर में अपना total comment में ज़रूर बताना!")


def _outro_voice(n: int) -> str:
    return f"{_HI.get(n, str(n))} में से कितने सही हुए? Comment में ज़रूर बताओ!"


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


def _mega_quiz(picked: list, n: int, n_questions: int = QUESTIONS_TARGET) -> dict:
    questions = [q["questions"][0] for q in picked][:n_questions]
    return {
        "key": "weekly_compilation", "format": "trivia", "concept": "geography",
        "title": f"{len(questions)} Ajab Gajab Sawaal — Kitne Sahi Kar Paoge? "
                 f"(Mega Quiz #{n})",
        "hook": _hook_card(len(questions)),
        "questions": questions,
    }


def _voice_lines(picked: list, n_questions: int = QUESTIONS_TARGET) -> list:
    """One Devanagari line per segment: intro + (ask, reveal)*N + outro."""
    lines = [_intro_voice(n_questions)]
    for q in picked[:n_questions]:
        lines += [q["voice"][1], q["voice"][2]]
    lines.append(_outro_voice(n_questions))
    return lines


def _thumbnail(accent: tuple, photo=None, n_questions: int = QUESTIONS_TARGET) -> str:
    """Photo-backed 16:9 clickbait thumbnail (Roman text — CI has no Devanagari
    font); falls back to the flat card when no photo was fetched."""
    W, H = 1280, 720
    if photo:
        img = Image.open(photo).convert("RGB")
        th = int(img.width * H / W)
        if th <= img.height:
            top = max((img.height - th) // 3, 0)
            img = img.crop((0, top, img.width, top + th))
        img = img.resize((W, H), Image.LANCZOS)
        grad = Image.new("L", (W, 1))
        for x in range(W):
            grad.putpixel((x, 0), int(215 - 155 * x / W))
        img = Image.composite(Image.new("RGB", (W, H), "#0B0B14"), img,
                              grad.resize((W, H)))
    else:
        img = Image.new("RGB", (W, H), "#12121C")
    d = ImageDraw.Draw(img)
    ax = "#%02X%02X%02X" % tuple(accent)
    d.rectangle([0, H - 22, W, H], fill=ax)
    d.text((64, 170), f"{n_questions} SAWAAL", font=load_font(120), fill="white",
           anchor="lm", stroke_width=6, stroke_fill="#0B0B14")
    d.text((64, 340), "SAARE SAHI", font=load_font(110), fill=ax,
           anchor="lm", stroke_width=6, stroke_fill="#0B0B14")
    d.text((64, 470), "KARKE DIKHAO!", font=load_font(86), fill="white",
           anchor="lm", stroke_width=5, stroke_fill="#0B0B14")
    d.text((64, 620), "99% LOG POORA SAHI NAHI KAR PATE", font=load_font(40),
           fill="#E5E7EB", anchor="lm", stroke_width=3, stroke_fill="#0B0B14")
    fd, p = tempfile.mkstemp(suffix=".png"); os.close(fd)
    img.save(p, "PNG")
    return p


async def _fit_under_shorts_cap(picked: list, n: int, audio_path: str):
    """Build the mega-quiz, dropping a sawaal at a time until narration plus
    countdown gaps fits under SHORTS_MAX_S.

    Over 3:00 YouTube treats the upload as a regular video, which on this
    channel means no feed distribution at all. The Hindi voice's pace varies a
    lot with the pre-baked line lengths, so a fixed count is not safe on its
    own. TTS is cheap; the render is not, so length is settled BEFORE rendering.
    """
    for n_q in range(QUESTIONS_TARGET, MIN_QUESTIONS - 1, -1):
        quiz = _mega_quiz(picked, n, n_q)
        segs = build_segments(quiz)
        voice = _voice_lines(picked, n_q)
        if len(voice) != len(segs):
            raise SystemExit(f"[Comp] voice/segment mismatch: {len(voice)} vs {len(segs)}")
        segs = [(k, qi, voice[i]) for i, (k, qi, _t) in enumerate(segs)]
        narration = " ".join(t for _k, _q, t in segs)
        duration, marks = await generate_voiceover(narration, audio_path)
        duration, marks = insert_countdown_gaps(audio_path, segs, marks, duration)
        if duration <= SHORTS_MAX_S:
            print(f"[Comp] {n_q} sawaal -> {duration:.0f}s (under the "
                  f"{SHORTS_MAX_S:.0f}s Shorts cap)")
            return quiz, segs, duration, marks
        print(f"[Comp] {n_q} sawaal -> {duration:.0f}s, over cap — dropping one")
    raise SystemExit(f"[Comp] cannot fit {MIN_QUESTIONS} sawaal under "
                     f"{SHORTS_MAX_S:.0f}s — aborting rather than posting long-form")


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
    temp_files = []
    try:
        fd, audio_path = tempfile.mkstemp(suffix=".mp3"); os.close(fd)
        temp_files.append(audio_path)
        quiz, segs, audio_duration, marks = await _fit_under_shorts_cap(
            picked, len(comp_rows) + 1, audio_path)
        if audio_duration < 60:
            raise RuntimeError("compilation voiceover suspiciously short")
        print(f"[Comp] {len(quiz['questions'])} sawaal, narration segs {len(segs)}")
        starts, _real = segment_starts(segs, audio_duration, marks)
        try:
            mix_quiz_sfx(audio_path, quiz["key"], audio_duration,
                         seg_starts=starts, quiz=quiz)
        except Exception as e:
            print(f"[Comp] SFX skipped: {e}")
        print(f"[Comp] narration {audio_duration/60:.1f} min "
              f"({'real TTS' if _real else 'word-share'} timings)")

        # 3-4 generic quiz-suitable photos rotating through the video;
        # switches snap to question boundaries.
        bg_files = []
        try:
            from backgrounds import fetch as fetch_bg
            for query in ("india gate monument evening", "colorful indian pattern art",
                          "night sky stars", "vintage world map"):
                fd, bp = tempfile.mkstemp(suffix=".jpg"); os.close(fd)
                temp_files.append(bp)
                try:
                    got = fetch_bg(query, [], "geography", bp, fmt="trivia")
                except Exception:
                    got = None
                if got:
                    bg_files.append(got)
        except Exception as e:
            print(f"[Comp] BG skipped: {e}")
        bg_arg = None
        if bg_files:
            ask_starts = [starts[i] for i, sg in enumerate(segs) if sg[0] == "ask"]
            def _snap(t):
                return min(ask_starts, key=lambda a: abs(a - t)) if ask_starts else t
            nb = len(bg_files)
            bounds = ([0.0] + [_snap(audio_duration * i / nb) for i in range(1, nb)]
                      + [audio_duration])
            bg_arg = [(bounds[i], bounds[i + 1], bg_files[i]) for i in range(nb)]
        print(f"[Comp] backgrounds: {len(bg_files)} photos")

        fd, video_path = tempfile.mkstemp(suffix=".mp4"); os.close(fd)
        temp_files.append(video_path)
        partial(render_quiz, quiz=quiz)(video_path, accent, audio_duration,
                                        seg_starts=starts, bg_image=bg_arg)

        # Low BGM bed (same tracks and 0.08 volume the daily pipeline mixes;
        # normalize=0 keeps the voice level). Video stays NATIVE 9:16 and is
        # stream-copied — the old 16:9 blurred-fill mux made this a landscape
        # video, which disqualified it as a Short. See the module docstring.
        fd, final_path = tempfile.mkstemp(suffix=".mp4"); os.close(fd)
        temp_files.append(final_path)
        import random as _rnd
        import subprocess
        music_dir = Path(__file__).parent / "music"
        tracks = sorted(music_dir.glob("*.mp3")) if music_dir.exists() else []
        cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path]
        if tracks:
            track = _rnd.choice(tracks)
            print(f"[Comp] BGM: {track.name}")
            cmd += ["-stream_loop", "-1", "-i", str(track)]
            afilter = ("[2:a]volume=0.08[m];"
                       "[1:a][m]amix=inputs=2:duration=first:"
                       "dropout_transition=3:normalize=0[aout]")
        else:
            afilter = "[1:a]anull[aout]"
        cmd += ["-filter_complex", afilter,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-shortest", final_path]
        subprocess.run(cmd, check=True, capture_output=True)
        try:
            from shared import _loudnorm_in_place
            _loudnorm_in_place(final_path)
        except Exception as e:
            print(f"[Comp] loudnorm skipped: {e}")

        n_q = len(quiz["questions"])
        thumb_path = _thumbnail(accent, photo=bg_files[0] if bg_files else None,
                                n_questions=n_q)
        temp_files.append(thumb_path)

        # No chapters: this is a Short now, and chapter timestamps neither
        # render nor help in the Shorts player.
        description = (
            f"{_hook_card(n_q)}\n\n"
            f"{_HI.get(n_q, str(n_q))} अजब-गजब सवाल — score comment में बताओ! "
            "रोज़ 4 नए facts ke liye subscribe karo.\n\n"
            f"#Shorts {TAGS_LINE}"
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
            "status": {"privacyStatus": PRIVACY,
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
        # posts its own score CTA sized to the final question count.
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
