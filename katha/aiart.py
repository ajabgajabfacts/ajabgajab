"""aiart.py: illustrated character scenes for a Short, from Cloudflare Workers AI (FLUX.1 [schnell], free tier).

Owner 2026-11-23: "lets put interesting click bait pictures". The story channels with 300k-3M median views in our
niches (Dev Kathan Shorts, The AI Historian, Behind The Legend) show illustrated close-ups of deities, heroes and
historical people with strong emotion. We showed Wikimedia photos of temples and stones (Ajab median ~90 views).

- One picture per sentence, from the script's "scenes" (the writer adds them; see write.py WRITE). If they are
  missing or the count is off, one Gemini text call writes them from the sentences.
- Scene 1 is an extreme close-up of the main character's face: it is the frame the feed shows first.
- One Gemini vision call vets the whole set (text in the image, broken faces or hands, gore, an undignified
  deity). A rejected picture is redrawn once; if it still fails, it is dropped and its line keeps the picture of
  the line before it (media.line_plan).
- FLUX.1 [schnell] is Apache-2.0, so monetised use is fine. The Workers AI free tier is 10,000 neurons/day; at 4 steps
  one 1024px image is ~58 neurons, so ~170 images/day. Ajab + WTR need ~60. Past the cap Cloudflare returns an
  error, never a bill, and we fall back to Wikimedia.

On only when CF_ACCOUNT_ID and CF_API_TOKEN are set (GitHub secrets) and AI_ART is not "0". Any failure returns
None and make.py uses the Wikimedia pictures as before, so a Cloudflare problem never stops a post. The token is
only ever sent in the Authorization header and never printed.

    python katha/aiart.py test "Hanuman roaring, extreme close-up"   # one picture -> ./aiart_test.jpg (needs CF_* env)
"""
import base64, io, json, os, sys, threading, time
from pathlib import Path

import requests
from PIL import Image

MODEL = "@cf/black-forest-labs/flux-1-schnell"
STEPS = 4
MIN_OK = 5               # fewer usable pictures than this: use Wikimedia instead
TIMEOUT = 90
SUFFIX = (". Vertical portrait framing, subject centred. No text, no letters, no captions, no signature, "
          "no watermark, no logo.")
STYLES = {
    "devotional": ("Epic Indian devotional digital painting, classical Raja Ravi Varma colours meeting modern "
                   "mythological concept art, rich saturated jewel tones, glowing rim light, intricate traditional "
                   "ornaments, highly detailed expressive face, cinematic depth of field"),
    "india": ("Cinematic historical illustration of India, painterly realism, dramatic golden-hour light, rich "
              "colours, period-accurate clothes and architecture, highly detailed expressive faces, film still"),
    "en": ("Cinematic historical illustration, painterly realism, dramatic chiaroscuro light, period-accurate "
           "clothes and setting, highly detailed expressive faces, muted film colour grade, movie still"),
}
DEVOTIONAL = {"myth", "saint", "folk"}
_SIZE_OK = [True]        # does the endpoint take width/height? Learned on the first call.
GEMINI_CAP_S = 120       # ai._call can sit in per-minute-limit waits for ~25 min; a Short has 30 min in all


def _capped(fn, cap=GEMINI_CAP_S):
    """fn() in a daemon thread; its result, or None after `cap` seconds or on any exception."""
    box = {}
    def run():
        try:
            box["v"] = fn()
        except Exception as e:
            box["e"] = e
    th = threading.Thread(target=run, daemon=True); th.start(); th.join(cap)
    if th.is_alive():
        print(f"[aiart] Gemini still busy after {cap}s: moving on"); return None
    if "e" in box:
        print(f"[aiart] Gemini call failed: {str(box['e'])[:120]}")
    return box.get("v")

SCENES = """You plan the pictures for a {lang_name} YouTube Short. One illustrated still per narration line.

LINES (the narration, in order):
{lines}

STORY FACTS (English): {facts}

Return JSON {{"scenes": ["exactly {n} English image prompts, one per line, same order"]}}.
Each prompt shows the main CHARACTER of that line in that moment: who, doing what, the face and its emotion, the
setting, the light, the camera framing. Scene 1 is an extreme close-up of the main character's face at the peak of
emotion (this frame decides whether people stop scrolling). Deities in their traditional iconography, dignified and
fully clothed. Period-accurate clothes and places. Never text, letters, logos, blood, gore or living people.
Under 60 words each."""

VET = """These {n} pictures (numbered 0 to {last} in order) illustrate a family-friendly story Short.
What each one should show:
{prompts}

Reject a picture ONLY for a real defect: visible text or letters, a deformed or doubled face, broken hands or limbs
that a viewer would notice, blood or gore, nudity, a deity shown undignified (wrong number of heads where it
matters, comic, partly clothed), or a picture that shows something clearly different from its line.
Return JSON {{"bad": [indices of rejected pictures], "why": ["one short reason per rejected index"]}}."""


def enabled():
    return bool(os.environ.get("CF_ACCOUNT_ID") and os.environ.get("CF_API_TOKEN")) and os.environ.get("AI_ART", "1") != "0"


def style(kind, lang):
    if lang == "en":
        return STYLES["en"]
    return STYLES["devotional"] if kind in DEVOTIONAL else STYLES["india"]


THUMB = (". Composition for a wide video thumbnail: the face and upper body fill the RIGHT half of the frame at mid "
         "height, the LEFT half is dark, empty background for a title. No text, no letters, no signature, no watermark.")


def thumbnail_image(scene, kind, lang):
    """One picture made for a long video's thumbnail (longform.thumbnail adds the title), or None."""
    if not enabled() or not scene:
        return None
    return generate(f"{scene.rstrip('. ')}. Extreme close-up at the peak of emotion. {style(kind, lang)}{THUMB}")


def generate(prompt):
    """One picture as a PIL image, or None. Never raises."""
    acct, tok = os.environ.get("CF_ACCOUNT_ID", ""), os.environ.get("CF_API_TOKEN", "")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{MODEL}"
    body = {"prompt": prompt[:2000], "steps": STEPS}
    for attempt in range(3):
        try:
            payload = dict(body, width=768, height=1344) if _SIZE_OK[0] else body
            r = requests.post(url, headers={"Authorization": f"Bearer {tok}"}, json=payload, timeout=TIMEOUT)
            if r.status_code == 400 and _SIZE_OK[0] and ("width" in r.text or "height" in r.text or "additional" in r.text):
                _SIZE_OK[0] = False; continue                     # this model takes no size: square it is
            if r.status_code == 429 or r.status_code >= 500:
                print(f"[aiart] HTTP {r.status_code}, retrying"); time.sleep(4 * (attempt + 1)); continue
            if r.status_code != 200:
                print(f"[aiart] HTTP {r.status_code}: {r.text[:160]}"); return None
            j = r.json()
            b64 = (j.get("result") or {}).get("image")
            if not b64:
                print(f"[aiart] no image in reply: {str(j)[:160]}"); return None
            return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        except Exception as e:
            print(f"[aiart] {type(e).__name__}: {str(e)[:120]}"); time.sleep(3)
    return None


def scene_prompts(script, lang_name, facts):
    sc = [x for x in (script.get("scenes") or []) if isinstance(x, str) and x.strip()]
    n = len(script["sentences"])
    if len(sc) == n:
        return sc
    import ai
    out = _capped(lambda: ai.json_call(SCENES.format(lang_name=lang_name, n=n, facts=facts[:1500],
                                                     lines="\n".join(f"{i}: {x}" for i, x in enumerate(script["sentences"]))),
                                       temperature=0.7)) or {}
    sc = [x for x in out.get("scenes", []) if isinstance(x, str) and x.strip()]
    if len(sc) == n:
        return sc
    if out:
        print(f"[aiart] Gemini gave {len(sc)} scenes for {n} lines")
    return claim_scenes(script, n)


def claim_scenes(script, n):
    """No Gemini needed: one scene per line from the English claims, which follow the story's order.
    Rougher than written scenes, but it keeps the illustrated look on a day Gemini is slow or out of quota."""
    claims = [c for c in script.get("claims_en", []) if isinstance(c, str) and c.strip()]
    if not claims:
        return None
    out = [f"{claims[0]} Shown as an extreme close-up of the main figure's face at the peak of emotion."]
    for i in range(1, n):
        c = claims[min(len(claims) - 1, round(i * len(claims) / n))]
        out.append(f"{c} Shown as one dramatic illustrated moment, focused on the people or creatures involved and "
                   f"what they are doing, expressive faces.")
    print("[aiart] scenes built from claims_en")
    return out


def vet(images, prompts):
    """Indices to redraw. A failed vet call rejects nothing (the pictures are usually fine; the post must go out)."""
    try:
        import ai
        parts = []
        for im in images:
            b = io.BytesIO(); im.convert("RGB").resize((384, int(384 * im.height / im.width))).save(b, "JPEG", quality=80)
            parts.append(ai.image_part(b.getvalue()))
        v = _capped(lambda: ai.json_call(VET.format(n=len(images), last=len(images) - 1,
                                                    prompts="\n".join(f"{i}: {p[:200]}" for i, p in enumerate(prompts))),
                                         models=ai.VISION_MODELS, parts=parts, temperature=0.1)) or {}
        bad = sorted({int(i) for i in v.get("bad", []) if str(i).lstrip("-").isdigit() and 0 <= int(i) < len(images)})
        if bad:
            print(f"[aiart] vet rejected {bad}: {v.get('why', [])}")
        return bad
    except Exception as e:
        print(f"[aiart] vet skipped: {str(e)[:120]}")
        return []


def shots(script, kind, lang, lang_name, facts, every=1):
    """Shot dicts in media.images' shape (img, lines, score, file, artist, license, ai=True), or None.
    every=2 draws one picture per two lines (long-form chapters: ~50 pictures a video instead of ~100, so a
    long-form day stays inside the free 10,000 neurons with the Shorts)."""
    if not enabled():
        return None
    prompts = scene_prompts(script, lang_name, facts)
    if not prompts:
        return None
    n = len(prompts)
    starts = list(range(0, n, max(1, every)))
    covers = {k: list(range(k, min(n, k + every))) for k in starts}
    prompts = [prompts[k] for k in starts]
    st = style(kind, lang)
    full = [f"{p.rstrip('. ')}. {st}{SUFFIX}" for p in prompts]
    t0 = time.time()
    imgs = []
    for i, p in enumerate(full):
        im = generate(p)
        if im is None and i == 0:
            print("[aiart] first picture failed: using Wikimedia"); return None
        imgs.append(im)
    have = [i for i, im in enumerate(imgs) if im is not None]
    redo = [have[i] for i in vet([imgs[i] for i in have], [prompts[i] for i in have])]
    for k in redo:
        imgs[k] = generate(full[k] + " Clean anatomy, natural hands, exactly as described.")
    redone = [k for k in redo if imgs[k] is not None]
    if redone:                       # a redraw is checked too (11-23 test: a redrawn Ravana came back with a fake signature)
        for i in vet([imgs[k] for k in redone], [prompts[k] for k in redone]):
            print(f"[aiart] redraw of {redone[i]} still rejected: dropped (its line keeps the picture before it)")
            imgs[redone[i]] = None
    if imgs[0] is None:
        return None
    out = [dict(img=im, lines=covers[starts[i]], score=9, file=f"File:AI illustration {i + 1}", artist="AI illustration",
                license="FLUX.1 schnell", ai=True, what=prompts[i][:120], where="", scene=prompts[i])
           for i, im in enumerate(imgs) if im is not None]
    print(f"[aiart] {len(out)}/{len(prompts)} pictures in {time.time() - t0:.0f}s ({imgs[0].size[0]}x{imgs[0].size[1]})")
    return out if len(out) >= min(MIN_OK, len(prompts) - 1) else None


if __name__ == "__main__":
    if sys.argv[1:2] == ["test"]:
        im = generate(" ".join(sys.argv[2:]) + ". " + STYLES["devotional"] + SUFFIX)
        print("FAILED" if im is None else f"ok {im.size}")
        if im is not None:
            im.save("aiart_test.jpg", quality=92)
