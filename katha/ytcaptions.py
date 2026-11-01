"""ytcaptions.py — upload a video's own script as its YouTube caption track (2026-11-01, owner approved).

The same file lives in quizora/, level3challenge/ and ajabgajab/katha/; keep the copies identical.

Why: none of the four channels uploaded captions, so YouTube only had auto-captions, which don't exist at all
for Telugu, Kannada, Odia and most Ajab languages and are guesswork elsewhere. We already know the exact
words and their timings (the burned-in captions), so the track is exact: YouTube can index what the video
says and offer auto-translated subtitles from it.

Cost: captions.insert is 400 quota units (an upload is 1600). It runs after the upload, comment and
playlist calls and never raises, so a failure (quota, a transient 5xx) costs the caption and nothing else.

    cues = [(start_s, end_s, "text"), ...]
    ytcaptions.upload(yt, video_id, cues, "te")
"""
import io


def _ts(t):
    ms = int(round(max(t, 0) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def srt(cues):
    out, n = [], 0
    for a, b, text in cues:
        text = " ".join(str(text).split())
        if not text or b - a < 0.15:
            continue
        n += 1
        out.append(f"{n}\n{_ts(a)} --> {_ts(b)}\n{text}\n")
    return "\n".join(out)


def sentence_cues(sentences, word_times, offset=0.0, max_words=10):
    """Cues from per-word (start, end) times over all sentences; long sentences split every max_words.
    Returns [] if the times don't line up with the words: a caption must never stop a post."""
    cues, k = [], 0
    try:
        for s in sentences:
            ws = s.split()
            for i in range(0, len(ws), max_words):
                chunk = ws[i:i + max_words]
                a, b = word_times[k + i][0], word_times[k + i + len(chunk) - 1][1]
                cues.append((offset + float(a), offset + float(b), " ".join(chunk)))
            k += len(ws)
    except Exception as e:
        print(f"[captions] no cues: {str(e)[:120]}")
        return []
    return cues


def upload(yt, video_id, cues, lang):
    """Insert the track (not a draft). Returns True on success; prints and returns False otherwise."""
    body = srt(cues or [])
    if not body:
        return False
    try:
        from googleapiclient.http import MediaIoBaseUpload
        media = MediaIoBaseUpload(io.BytesIO(body.encode("utf-8")), mimetype="application/octet-stream",
                                  resumable=False)
        yt.captions().insert(part="snippet", body={"snippet": {
            "videoId": video_id, "language": lang, "name": "", "isDraft": False}},
            media_body=media).execute()
        print(f"[captions] {body.count(' --> ')} cues uploaded ({lang})")
        return True
    except Exception as e:
        print(f"[captions] not uploaded: {str(e)[:160]}")
        return False
