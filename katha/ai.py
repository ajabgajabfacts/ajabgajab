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
    for f in ("ajabgajab/gemini_api.txt", "quizora/gemini_api.txt"):
        p = root / f
        if p.exists():
            ks.append(p.read_text().strip())
    return list(dict.fromkeys(k for k in ks if k))


KEYS = _keys()
_ki = 0
_client = genai.Client(api_key=KEYS[0]) if KEYS else None


def _call(models, contents, config):
    """Try each model; on a daily-quota 429 move to the next key. Raises the last error."""
    global _ki, _client
    last = None
    for m in models:
        for attempt in range(3):
            try:
                return _client.models.generate_content(model=m, contents=contents, config=config)
            except Exception as e:
                last = e; s = str(e)
                if "PerDay" in s and _ki + 1 < len(KEYS):
                    _ki += 1; _client = genai.Client(api_key=KEYS[_ki]); continue
                if "429" in s or "503" in s or "500" in s:
                    time.sleep(8 * (attempt + 1)); continue
                break                                    # 404/400: this model won't work, try the next
    raise last


def json_call(prompt, models=TEXT_MODELS, parts=None, temperature=0.9):
    cfg = gt.GenerateContentConfig(response_mime_type="application/json", temperature=temperature)
    contents = (parts or []) + [prompt]
    r = _call(models, contents, cfg)
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
    r = _call(TTS_MODELS, [text], cfg)
    p = r.candidates[0].content.parts[0].inline_data
    if p.data[:4] == b"RIFF":
        return p.data
    import io, re, wave                                   # older models return raw PCM
    rate = int((re.search(r"rate=(\d+)", p.mime_type or "") or [0, 24000])[1])
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(p.data)
    return b.getvalue()
