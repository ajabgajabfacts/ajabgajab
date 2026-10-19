"""Gemini access: key rotation across projects, model fallback, JSON calls."""
import json, os, time
from pathlib import Path
from google import genai
from google.genai import types as gt

TEXT_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"]
VISION_MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest"]
TTS_MODELS = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]


def _keys():
    ks = [os.environ.get("GEMINI_API_KEY", "")]
    root = Path(__file__).resolve().parents[2]          # YT_project, when run locally
    # Ajab Gajab's own key only. Quizora's quota funds Quizora's daily narration and
    # must never be spent here (it ran dry on 3.8-flash on 2026-10-19).
    for f in ("ajabgajab/gemini_api.txt",):
        p = root / f
        if p.exists():
            ks.append(p.read_text().strip())
    return list(dict.fromkeys(k for k in ks if k))


KEYS = _keys()
_ki = 0
# The SDK has NO default timeout: an overloaded model (3.8-flash took 37 s to say "OK"
# on 2026-10-19) hung a long-form run for 25 min. Every call is bounded and falls back.
TIMEOUT_MS = {"text": 90_000, "vision": 45_000, "tts": 180_000}


def _mk(key):
    return {k: genai.Client(api_key=key, http_options=gt.HttpOptions(timeout=v)) for k, v in TIMEOUT_MS.items()}


_client = _mk(KEYS[0]) if KEYS else None


_last_call = [0.0]
MIN_GAP_S = 4.0          # free-tier per-minute limits: ~15 RPM; long-form bursts tripped them


def _pace():
    wait = _last_call[0] + MIN_GAP_S - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def _call(models, contents, config, kind="text"):
    """Try each model in turn.
    - per-MINUTE quota (429 ...PerMinute...): wait and retry the SAME model. Treating it as
      "move on" cascaded through every model in seconds and skipped 48 stories (2026-10-19).
    - per-DAY quota: next key if there is one, else next model.
    - timeout: next model. 5xx: brief backoff, retry."""
    global _ki, _client
    last = None
    for m in models:
        attempt = 0
        while attempt < 5:
            attempt += 1
            _pace()
            try:
                return _client[kind].models.generate_content(model=m, contents=contents, config=config)
            except Exception as e:
                last = e; s = str(e)
                if "RESOURCE_EXHAUSTED" in s or "429" in s:
                    if "PerDay" in s or "per_day" in s.lower():
                        if _ki + 1 < len(KEYS):
                            _ki += 1; _client = _mk(KEYS[_ki]); attempt = 0; continue
                        print(f"[ai] {m}: daily quota spent -> next model"); break
                    print(f"[ai] {m}: per-minute limit, waiting 35s"); time.sleep(35); continue
                if "imeout" in s or "timed out" in s:
                    print(f"[ai] {m}: timeout -> next model"); break
                if "503" in s or "500" in s:
                    time.sleep(6 * attempt); continue
                break                                    # 404/400: this model won't work, try the next
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
