"""aiart.py: illustrated character scenes for a Short or a long video, from Cloudflare Workers AI (free tier).

Owner 2026-11-23: "lets put interesting click bait pictures". The story channels with 300k-3M median views in our
niches (Dev Kathan Shorts, The AI Historian, Behind The Legend) show illustrated close-ups of deities, heroes and
historical people with strong emotion. We showed Wikimedia photos of temples and stones (Ajab median ~90 views).

Model (11-23, after the owner saw a test "Hanuman" that "doesnt even look like hanuman"):
- FLUX.2 [klein] 4B: Apache-2.0 (monetised use is fine), takes width/height (true 9:16 and 16:9), and drew a
  recognisable Hanuman (monkey face, tail, mace) where FLUX.1 [schnell] drew a bearded man. schnell stays as the
  fallback (square only). FLUX.2 klein 9B looked as good but is under the FLUX Non-Commercial License, whose output
  terms are disputed: never use it on these monetised channels.
- ICONS: the defining look of ~30 deities and epic figures is appended to any prompt that names them, and the vet
  rejects a named figure drawn without it. Devotional scenes frame deities from the waist up, where the models keep
  the face right.
- Cost: klein-4b bills ~26 neurons per 512x512 output tile. Sizes are exact multiples of 512 so the bill is clear:
  the opening frame 1024x2048 (8 tiles), every other line 512x1024 (2 tiles): ~620 neurons per 9-line Short,
  ~4,400/day for Ajab + WTR. Long-form chapters 1024x512 (one per two lines), ~2,600 per video. The free tier is
  10,000/day; past it Cloudflare returns an error (never a bill) and we fall back to Wikimedia.

- One picture per sentence, from the script's "scenes" (write.py WRITE asks for them). Missing: one Gemini call
  (capped at 2 min) writes them, else they are built from claims_en.
- One Gemini vision call vets the set; a rejected picture is redrawn once and checked again; still bad = dropped and
  its line keeps the picture before it (media.line_plan).

On only when CF_ACCOUNT_ID and CF_API_TOKEN are set (GitHub secrets) and AI_ART is not "0" (repo variable). Any
failure returns None and the caller uses Wikimedia, so a Cloudflare problem never stops a post. The token is only
sent in the Authorization header and never printed.

    python katha/aiart.py test "Hanuman lifting the mountain"   # -> ./aiart_test.jpg (needs the CF_* env)
"""
import base64, io, json, os, re, sys, threading, time
from pathlib import Path

import requests
from PIL import Image

KLEIN = "@cf/black-forest-labs/flux-2-klein-4b"
SCHNELL = "@cf/black-forest-labs/flux-1-schnell"
HOOK_SIZE, LINE_SIZE = (1024, 2048), (512, 1024)          # Shorts: opening frame sharp, the rest cheap
WIDE_SIZE, THUMB_SIZE = (1024, 512), (2048, 1024)          # long-form chapters, long-form thumbnail
MIN_OK = 5               # fewer usable pictures than this: use Wikimedia instead
TIMEOUT = 120
NO_TEXT = " No text, no letters, no captions, no signature, no watermark, no logo."
STYLES = {
    # "calendar-art" drew flat, children's-book pictures (11-23 test); this reads like the Dev Kathan look.
    "devotional": ("Cinematic semi-realistic mythological digital painting, epic scale, dramatic volumetric light and "
                   "god rays, rich deep colours, detailed skin and fabric textures, highly detailed expressive face, "
                   "movie-poster quality"),
    "india": ("Cinematic historical illustration of India, painterly realism, dramatic golden-hour light, rich "
              "colours, period-accurate clothes and architecture, highly detailed expressive faces, film still"),
    "en": ("Cinematic historical illustration, painterly realism, dramatic chiaroscuro light, period-accurate "
           "clothes and setting, highly detailed expressive faces, muted film colour grade, movie still"),
}
DEVOTIONAL = {"myth", "saint", "folk"}
DEITY_FRAMING = " Show any deity from the waist or chest up with the face clearly visible, dignified and fully clothed."
GEMINI_CAP_S = 120       # ai._call can sit in per-minute-limit waits for ~25 min; a Short has 30 min in all

# The look viewers expect. Matched as whole words in the (English) scene prompt; the first name is the label.
ICONS = [
    (("Hanuman", "Anjaneya", "Maruti", "Bajrangbali"),
     "a vanara deity with a MONKEY face and short muzzle, reddish-orange fur, a long monkey tail, golden crown and "
     "earrings, a golden gada mace, muscular, saffron dhoti"),
    (("Shiva", "Shiv", "Mahadeva", "Shankar", "Bholenath"),
     "blue-grey skin, a third eye on the forehead, matted hair piled high with a crescent moon and the Ganga stream, a "
     "cobra around his neck, rudraksha beads, tiger-skin cloth, a trident (trishul) and a damaru drum"),
    (("Vishnu", "Narayana"),
     "blue skin, four arms holding a conch, the Sudarshana discus, a mace and a lotus, tall golden crown, yellow silk"),
    (("Krishna",), "blue skin, a peacock feather in his crown, a bamboo flute, yellow silk, garland"),
    (("Rama", "Sri Rama", "Lord Ram"), "blue-green skin, princely crown, a great bow and a quiver of arrows, calm noble face"),
    (("Sita",), "a princess in a red or saffron sari with gold jewellery, gentle face"),
    (("Lakshmana",), "a fair-skinned prince with a bow and arrows and a crown"),
    (("Ravana",), "a demon king with TEN crowned heads side by side and many arms, gold armour"),
    (("Ganesha", "Ganesh", "Ganapati", "Vinayaka"),
     "an ELEPHANT head with one broken tusk, a round belly, four arms, a modak sweet, a small mouse beside him"),
    (("Durga",), "a goddess with eight or ten arms each holding a weapon, riding a lion, red sari, crown, calm fierce face"),
    (("Kali",), "a goddess with dark blue skin, wild loose hair, red tongue out, many arms, a sword"),
    (("Lakshmi",), "a goddess in a red sari seated on a pink lotus, four arms, gold coins flowing from one hand"),
    (("Saraswati",), "a goddess in a white sari playing a veena, seated on a white lotus, a swan beside her"),
    (("Parvati",), "a goddess in a red sari with a crown and a gentle face"),
    (("Brahma",), "FOUR bearded faces, four arms holding the Vedas, seated on a lotus"),
    (("Narasimha",), "a LION head and mane on a man's body, fierce"),
    (("Murugan", "Kartikeya", "Subramanya", "Skanda"), "a youthful god holding a tall vel spear, a peacock beside him, crown"),
    (("Ayyappa", "Ayyappan", "Manikandan"),
     "a youthful god seated in a yoga posture with a band around his knees, crown, a tiger nearby"),
    (("Garuda",), "an eagle-man with a golden beak and great wings on a human body, crown"),
    (("Jatayu", "Sampati"), "a giant old VULTURE with huge wings and a jewelled crown"),
    (("Nandi",), "a white bull with decorations, kneeling"),
    (("Jagannath", "Jagannatha"), "the wooden deity with a black face, huge round white eyes and a wide red smile"),
    (("Venkateswara", "Balaji", "Srinivasa"),
     "a dark-skinned god with a tall golden crown, a broad white tilak covering his eyes, four arms with conch and discus"),
    (("Vitthala", "Vithoba", "Pandurang"), "a dark-skinned god standing on a brick with his hands on his hips, tall crown"),
    (("Buddha",), "a meditating monk with curled hair, long earlobes and a serene face, saffron robe"),
    (("Arjuna",), "a warrior prince with the great Gandiva bow"),
    (("Karna",), "a warrior with golden armour and golden earrings fused to his body"),
    (("Bhima",), "a huge muscular warrior with a heavy mace"),
    (("Indra",), "king of the gods with a golden crown, a thunderbolt (vajra), riding a white elephant"),
    (("Surya",), "the sun god with a radiant halo riding a chariot drawn by seven horses"),
]
# A name followed by river/district/dam (the Krishna or Bhima river) is a place, not the figure.
_ICON_RE = [(names, desc, re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b(?!\s+(river|district|dam|basin|delta|valley|nagar))",
                                     re.I)) for names, desc in ICONS]


def icons_in(text):
    """[(label, look)] for each figure the text names (max 3, first-mentioned first)."""
    hits = []
    for names, desc, rx in _ICON_RE:
        m = rx.search(text or "")
        if m:
            hits.append((m.start(), names[0], desc))
    return [(label, desc) for _, label, desc in sorted(hits)[:3]]


def iconify(prompt):
    found = icons_in(prompt)
    return prompt + "".join(f" {label} is depicted as {desc}." for label, desc in found)


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
Each prompt shows the main CHARACTER of that line in that moment: who (by name), doing what, the face and its emotion,
the setting, the light, the camera framing. Scene 1 is an extreme close-up of the main character's face at the peak of
emotion (this frame decides whether people stop scrolling). Deities in their traditional iconography, dignified and
fully clothed. Period-accurate clothes and places. Never text, letters, logos, blood, gore or living people.
Under 60 words each."""

VET = """These {n} pictures (numbered 0 to {last} in order) illustrate a family-friendly story Short.
What each one should show:
{prompts}

Reject a picture ONLY for a real defect:
- visible text, letters or a signature
- a deformed or doubled face, or broken hands or limbs a viewer would notice
- blood, gore or nudity
- a named deity or epic figure drawn WITHOUT the defining look written above (e.g. Hanuman with a human face instead
  of a monkey face, Ganesha without an elephant head, Ravana without ten heads), or shown undignified or comic
- something clearly different from what the line describes
Return JSON {{"bad": [indices of rejected pictures], "why": ["one short reason per rejected index"]}}."""


def enabled():
    return bool(os.environ.get("CF_ACCOUNT_ID") and os.environ.get("CF_API_TOKEN")) and os.environ.get("AI_ART", "1") != "0"


def style(kind, lang):
    if lang == "en":
        return STYLES["en"]
    return STYLES["devotional"] if kind in DEVOTIONAL else STYLES["india"]


def compose(scene, kind, lang, framing=""):
    """The full prompt: scene + the look of any named figure + style + framing + no-text."""
    extra = DEITY_FRAMING if (kind in DEVOTIONAL and lang != "en") or icons_in(scene) else ""
    return f"{iconify(scene.rstrip('. ') + '.')} {style(kind, lang)}.{extra}{framing}{NO_TEXT}"


# "dark, empty" came back as a hard black block (11-23); a soft continuation of the scene reads as one picture.
THUMB = (" Composition for a wide video thumbnail: the face and upper body fill the RIGHT half of the frame; the LEFT "
         "half continues the same scene (sky, clouds or background) but softly out of focus and darker, with no "
         "objects in it, so a title can sit there.")


def thumbnail_image(scene, kind, lang):
    """One picture made for a long video's thumbnail (longform.thumbnail adds the title), or None."""
    if not enabled() or not scene:
        return None
    return generate(compose(scene + ". Extreme close-up at the peak of emotion", kind, lang, THUMB), THUMB_SIZE)


def _run(model, prompt, size):
    """(image or None, retryable). klein takes multipart form data with a size; schnell takes JSON, square only."""
    acct, tok = os.environ.get("CF_ACCOUNT_ID", ""), os.environ.get("CF_API_TOKEN", "")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"
    hdr = {"Authorization": f"Bearer {tok}"}
    if model == KLEIN:
        r = requests.post(url, headers=hdr, timeout=TIMEOUT, files={
            "prompt": (None, prompt[:2000]), "width": (None, str(size[0])), "height": (None, str(size[1]))})
    else:
        r = requests.post(url, headers=hdr, timeout=TIMEOUT, json={"prompt": prompt[:2000], "steps": 4})
    if r.status_code == 429 or r.status_code >= 500:
        print(f"[aiart] {model.split('/')[-1]} HTTP {r.status_code}: {r.text[:120]}")
        return None, True
    if r.status_code != 200:
        print(f"[aiart] {model.split('/')[-1]} HTTP {r.status_code}: {r.text[:160]}")
        return None, False
    if "json" not in r.headers.get("content-type", ""):
        return Image.open(io.BytesIO(r.content)).convert("RGB"), False
    b64 = (r.json().get("result") or {}).get("image")
    if not b64:
        print(f"[aiart] no image in reply: {r.text[:160]}")
        return None, False
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"), False


def generate(prompt, size=LINE_SIZE):
    """One picture as a PIL image, or None. klein-4b first, schnell as the fallback. Never raises."""
    for model in (KLEIN, SCHNELL):
        for attempt in range(2):
            try:
                im, retry = _run(model, prompt, size)
                if im is not None:
                    return im
                if not retry:
                    break
                time.sleep(4 * (attempt + 1))
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
    """Indices to redraw. A failed vet call rejects nothing (the post must go out)."""
    try:
        import ai
        parts = []
        for im in images:
            b = io.BytesIO(); im.convert("RGB").resize((384, int(384 * im.height / im.width))).save(b, "JPEG", quality=80)
            parts.append(ai.image_part(b.getvalue()))
        lines = "\n".join(f"{i}: {iconify(p)[:420]}" for i, p in enumerate(prompts))
        v = _capped(lambda: ai.json_call(VET.format(n=len(images), last=len(images) - 1, prompts=lines),
                                         models=ai.VISION_MODELS, parts=parts, temperature=0.1)) or {}
        bad = sorted({int(i) for i in v.get("bad", []) if str(i).lstrip("-").isdigit() and 0 <= int(i) < len(images)})
        if bad:
            print(f"[aiart] vet rejected {bad}: {v.get('why', [])}")
        return bad
    except Exception as e:
        print(f"[aiart] vet skipped: {str(e)[:120]}")
        return []


def shots(script, kind, lang, lang_name, facts, every=1, wide=False):
    """Shot dicts in media.images' shape (img, lines, score, file, artist, license, ai=True), or None.
    every=2 draws one picture per two lines; wide=True draws 16:9 pictures (long-form chapters)."""
    if not enabled():
        return None
    prompts = scene_prompts(script, lang_name, facts)
    if not prompts:
        return None
    n = len(prompts)
    starts = list(range(0, n, max(1, every)))
    covers = {k: list(range(k, min(n, k + every))) for k in starts}
    prompts = [prompts[k] for k in starts]
    full = [compose(p, kind, lang) for p in prompts]
    sizes = [WIDE_SIZE if wide else (HOOK_SIZE if i == 0 else LINE_SIZE) for i in range(len(full))]
    t0 = time.time()
    imgs = []
    for i, p in enumerate(full):
        im = generate(p, sizes[i])
        if im is None and i == 0:
            print("[aiart] first picture failed: using Wikimedia"); return None
        imgs.append(im)
    have = [i for i, im in enumerate(imgs) if im is not None]
    redo = [have[i] for i in vet([imgs[i] for i in have], [prompts[i] for i in have])]
    for k in redo:
        imgs[k] = generate(full[k] + " Clean anatomy, natural hands, exactly as described.", sizes[k])
    redone = [k for k in redo if imgs[k] is not None]
    if redone:                       # a redraw is checked too (11-23 test: a redrawn Ravana came back with a fake signature)
        for i in vet([imgs[k] for k in redone], [prompts[k] for k in redone]):
            print(f"[aiart] redraw of {redone[i]} still rejected: dropped (its line keeps the picture before it)")
            imgs[redone[i]] = None
    if imgs[0] is None:
        return None
    out = [dict(img=im, lines=covers[starts[i]], score=9, file=f"File:AI illustration {i + 1}", artist="AI illustration",
                license="FLUX.2 klein 4B", ai=True, what=prompts[i][:120], where="", scene=prompts[i])
           for i, im in enumerate(imgs) if im is not None]
    print(f"[aiart] {len(out)}/{len(prompts)} pictures in {time.time() - t0:.0f}s (first {imgs[0].size[0]}x{imgs[0].size[1]})")
    return out if len(out) >= min(MIN_OK, len(prompts) - 1) else None


if __name__ == "__main__":
    if sys.argv[1:2] == ["test"]:
        im = generate(compose(" ".join(sys.argv[2:]), "myth", "hi"), HOOK_SIZE)
        print("FAILED" if im is None else f"ok {im.size}")
        if im is not None:
            im.save("aiart_test.jpg", quality=92)
