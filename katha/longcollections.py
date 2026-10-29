"""Long-form collections, rotation and the intro/outro prompt (split out of longform.py on 2026-10-29).

Kept free of the render stack so the Claude routine can plan long-forms (longplan.py) with only bank.py.
"""
import json
from pathlib import Path

import bank

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "longform_ledger.json"

# Collections. `pool(lang)` returns candidate stories in preference order; regional
# stories are welcome in any language in long-form (a Tamil viewer will watch 9
# minutes about Konark), but the language's own region goes first.
def _by(kinds=None, keys=None):
    def pool(lang):
        c = [s for s in bank.S if (keys and s["key"] in keys) or (kinds and s["kind"] in kinds)]
        return sorted(c, key=lambda s: (s["lang"] not in (lang,), s["lang"] != "all"))
    return pool

COLLECTIONS = {
    "mysteries": dict(theme="India's most mysterious and unbelievable places", pool=_by(kinds={"wonder", "folk"})),
    "mahabharata": dict(theme="untold stories of the Mahabharata", pool=_by(keys={
        "ekalavya", "karna_kavacha", "barbarika", "bhishma_vow", "abhimanyu", "ashwatthama", "gandhari", "yaksha_prashna",
        "draupadi_akshaya", "karna_after", "krishna_last_day", "samba_pestle", "ganesha_scribe"})),
    "gods": dict(theme="surprising stories of the gods and their families", pool=_by(keys={
        "ganesha_head", "ganesha_kartikeya_race", "riddhi_siddhi", "kartikeya_wives", "hanuman_sun", "hanuman_son",
        "shiva_ganga_jata", "alakshmi", "garuda_vishnu", "ravana_kailash", "vamana_bali", "samudra_manthan", "parashurama"})),
    "devotion": dict(theme="legends of devotion that moved the gods", pool=_by(keys={
        "gajendra_moksha", "dhruva", "prahlada_narasimha", "prahlad_after", "markandeya", "savitri_satyavan", "nachiketa",
        "sudama", "shabari", "jatayu", "kannappa", "meera", "tukaram", "kanhopatra", "andal", "narsinh_mehta"})),
    "marvels": dict(theme="India's mind-blowing engineering, science and space feats", pool=_by(kinds={"engineering", "space", "science"})),
    "wild": dict(theme="India's most incredible animals and natural wonders", pool=_by(kinds={"animal", "nature"})),
    "legends": dict(theme="real Indian legends - kings, queens, saints and sportspeople", pool=_by(kinds={"history", "saint", "sport", "people"})),
    "food": dict(theme="the surprising origins of India's favourite foods", pool=_by(kinds={"food"})),
}
ORDER = ["mysteries", "gods", "marvels", "mahabharata", "wild", "devotion", "legends", "food"]

FRAME = """You write the opening and closing of a {lang_name} YouTube story video for {audience}.
Theme: {theme}. The chapters, in order (their {lang_name} titles):
{chapters}

Write in natural spoken {lang_name}, native script. Do NOT state any fact that is not in a chapter title:
the intro TEASES, it never informs.
Return JSON:
{{"title": "{lang_name} video title, max 70 chars, curiosity-driven, true to the chapters",
 "intro": ["3-4 short spoken sentences, 35-55 words total: a gripping hook for the whole video, teasing 2-3 chapters"],
 "outro": ["2 sentences: ask which story amazed them most (comment), then a short line to subscribe for more stories"],
 "thumb_text": "2-4 punchy words in {lang_name} for the thumbnail",
 "kicker": "1-2 word {lang_name} label for the series, like STORIES / MYSTERIES",
 "chapter_word": "the {lang_name} word for 'chapter'",
 "intro_label": "the {lang_name} word for 'introduction'",
 "outro_label": "the {lang_name} word for 'conclusion'",
 "subscribe": "max 3 words in {lang_name}: subscribe",
 "description": "3 lines in {lang_name} describing the video",
 "hashtags": ["6 hashtags without #, mix {lang_name} and English"]}}"""


def ledger():
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []


def pick_collection(lang, force=None):
    if force:
        return force
    n = len([r for r in ledger() if r["lang"] == lang])
    return ORDER[n % len(ORDER)]
