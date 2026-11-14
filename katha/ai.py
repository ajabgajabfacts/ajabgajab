"""Gemini access: key rotation across projects, model fallback, JSON calls."""
import json, os, time
from pathlib import Path
from google import genai
from google.genai import types as gt

# Free tier = ~20 requests/day PER MODEL PER PROJECT for the flash models (found 2026-10-19:
# "GenerateRequestsPerDayPerProjectPerModel-FreeTier, limit 20"). Capacity therefore comes
# from spreading calls over several models and two projects, not from retrying one.
# gemini-4-hydrogen (2026-11-14): the one Gemini 4 model on the free tier (Carbon/Argon have no free quota). Its own
# 20/day per project adds capacity; second in each chain until a quality comparison says it should lead.
TEXT_MODELS = ["gemini-3.8-flash", "gemini-4-hydrogen", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3-flash-preview",
               "gemini-3.5-flash", "gemini-flash-latest"]
# The checker starts on a different model family from the writer: more capacity, and a
# more independent second opinion.
CHECK_MODELS = ["gemini-3.5-flash", "gemini-4-hydrogen", "gemini-3.6-flash", "gemini-3-flash-preview", "gemini-3.7-flash",
                "gemini-3.8-flash", "gemini-flash-latest"]
VISION_MODELS = ["gemini-3.5-flash-lite", "gemini-4-hydrogen", "gemini-3.1-flash-lite", "gemini-flash-lite-latest"]   # hydrogen reads images (tested 11-14)
TTS_MODELS = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]


def _keys():
    """Ajab Gajab's key, then Money Sorted's (that channel is paused; its quota is idle).
    Never Quizora's: its quota funds Quizora's daily narration."""
    ks = [os.environ.get("GEMINI_API_KEY", ""), os.environ.get("GEMINI_API_KEY_2", "")]
    root = Path(__file__).resolve().parents[2]          # YT_project, when run locally
    p = root / "ajabgajab/gemini_api.txt"
    if p.exists():
        ks.append(p.read_text().strip())
    env = root / "week_test/files/.env"
    if env.exists():
        for ln in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ln.startswith("GEMINI_API_KEY="):
                ks.append(ln.split("=", 1)[1].strip().strip('"'))
    return list(dict.fromkeys(k for k in ks if k))


KEYS = _keys()
# The SDK has NO default timeout: an overloaded model (3.8-flash took 37 s to say "OK"
# on 2026-10-19) hung a long-form run for 25 min. Every call is bounded.
TIMEOUT_MS = {"text": 90_000, "vision": 45_000, "tts": 180_000}
_clients = {}
_spent = set()                                   # (key index, model) whose daily quota is gone
_last_call = [0.0]
MIN_GAP_S = 4.0                                  # stay under the per-minute limits too


def _client(ki, kind):
    if (ki, kind) not in _clients:
        _clients[(ki, kind)] = genai.Client(api_key=KEYS[ki], http_options=gt.HttpOptions(timeout=TIMEOUT_MS[kind]))
    return _clients[(ki, kind)]


def _pace():
    wait = _last_call[0] + MIN_GAP_S - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def _call(models, contents, config, kind="text"):
    """Each model on each key, in order.
    - per-DAY quota: remember (key, model) as spent and move on.
    - per-MINUTE quota: wait and retry the same pair (treating it as "move on" once cascaded
      through every model in seconds and skipped 48 stories).
    - timeout: next model. 5xx: brief backoff and retry."""
    last = None
    for m in models:
        for ki in range(len(KEYS)):
            if (ki, m) in _spent:
                continue
            for attempt in range(1, 5):
                _pace()
                try:
                    return _client(ki, kind).models.generate_content(model=m, contents=contents, config=config)
                except Exception as e:
                    last = e; s = str(e)
                    if "RESOURCE_EXHAUSTED" in s or "429" in s:
                        if "PerDay" in s:
                            _spent.add((ki, m)); print(f"[ai] {m} key{ki + 1}: daily quota spent"); break
                        print(f"[ai] {m} key{ki + 1}: per-minute limit, waiting 35s"); time.sleep(35); continue
                    if "imeout" in s or "timed out" in s:
                        print(f"[ai] {m}: timeout"); break
                    if "503" in s or "500" in s:
                        time.sleep(6 * attempt); continue
                    break                                # 404/400: not usable, next
            else:
                continue
    if last is None:
        raise RuntimeError("all Gemini models/keys exhausted for today")
    raise last


def json_call(prompt, models=TEXT_MODELS, parts=None, temperature=0.9):
    cfg = gt.GenerateContentConfig(response_mime_type="application/json", temperature=temperature)
    contents = (parts or []) + [prompt]
    r = _call(models, contents, cfg, kind="vision" if models is VISION_MODELS else "text")
    out = json.loads(r.text)
    if isinstance(out, list):                    # models sometimes wrap the object in a list
        out = next((x for x in out if isinstance(x, dict)), {})
    return out


def image_part(jpeg_bytes):
    return gt.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")


def tts(text, voice="Charon"):
    """WAV bytes. The TTS models read any style instruction aloud, so the text is sent bare."""
    cfg = gt.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=gt.SpeechConfig(
        voice_config=gt.VoiceConfig(prebuilt_voice_config=gt.PrebuiltVoiceConfig(voice_name=voice))))
    r = _call(TTS_MODELS, [text], cfg, kind="tts")
    p = r.candidates[0].content.parts[0].inline_data
    if p.data[:4] == b"RIFF":
        return p.data
    import io, re, wave                                   # older models return raw PCM
    rate = int((re.search(r"rate=(\d+)", p.mime_type or "") or [0, 24000])[1])
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(p.data)
    return b.getvalue()
