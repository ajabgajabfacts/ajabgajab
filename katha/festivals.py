"""festivals.py — festival calendar (not calendar.py: that would shadow the stdlib module google-auth uses): Ajab posts each festival's stories in its region's language while the region is living it.

Owner 2026-11-01 ("go all in"), after the YPP analysis: our only breakouts ever were the Kannada Mysore Palace
(89k) and Dasara elephant (28k) Shorts, both posted on the Jamboo Savari day (Mysuru Dasara, 11-21 Oct 2026);
the next best Ajab Short is 1.9k, and ~600 Shorts on the other three channels never passed 4.4k. The bet: an
iconic place or story of a festival, in that region's language, in the days the whole region talks about it.
Measured as Shorts over 10,000 views per week; checkpoint 2026-11-30.

How it plugs in (make.py / prewrite.py):
  - make.pick(lang, day): an active event's unposted story for that language goes before anything else.
  - make.slot_lang: the rotating slots (1, 2) take the languages active events need, in the order listed
    here; slot 0 stays Kannada and slot 3 Telugu, and both pick their own events' stories.
  - prewrite.plan(): writes tomorrow's festival scripts a day ahead, ahead of any stock already written.
Each story is told once per language (the ledger), so a long window simply runs out and normal picks resume.

Dates: Drik Panchang / news (2026-11-01). Where sources disagree the window covers both days (Karthigai
Deepam 23/24 Nov; Vaikunta Ekadashi 20 Dec in most sources). Windows run from the day before to the day itself.
"""
import datetime as dt

D = dt.date
EVENTS = [
    # (name, first day, last day, {lang: [story keys, best first]}): the day before through the day itself,
    # because both Mysore hits went up ON the festival day (the feed picks a Short up within hours).
    ("Karnataka Rajyotsava", D(2026, 11, 1), D(2026, 11, 1), {"kn": ["rajyotsava_ekikarana"]}),
    # Diwali 2026: Naraka Chaturdashi 7 Nov, Lakshmi Puja 8 Nov, Bali Padyami / Govardhan 9-10 Nov.
    ("Naraka Chaturdashi", D(2026, 11, 6), D(2026, 11, 8), {
        "kn": ["narakasura"], "ta": ["narakasura"], "te": ["narakasura"], "mr": ["narakasura"]}),
    ("Diwali night", D(2026, 11, 7), D(2026, 11, 8), {
        "hi": ["diwali_ayodhya"], "bn": ["kali_puja"], "pa": ["bandi_chhor"]}),
    ("Bali Padyami / Annakut", D(2026, 11, 9), D(2026, 11, 10), {"kn": ["balipratipada"], "gu": ["govardhan"]}),
    ("Karthika Masam begins", D(2026, 11, 9), D(2026, 11, 11), {"te": ["srisailam_karthika"]}),
    ("Chhath", D(2026, 11, 13), D(2026, 11, 15), {"hi": ["chhath_deo"]}),
    ("Sabarimala season opens", D(2026, 11, 15), D(2026, 11, 17), {
        "ml": ["sabarimala_pathinettam", "ayyappan"], "ta": ["ayyappan"], "kn": ["ayyappan"]}),
    ("Karthigai Deepam / Karthika Pournami", D(2026, 11, 22), D(2026, 11, 24), {
        "ta": ["tiruvannamalai_deepam"], "te": ["pancharama"]}),
    ("Guru Nanak Jayanti", D(2026, 11, 23), D(2026, 11, 24), {"pa": ["guru_nanak"]}),
    ("Vaikunta Ekadashi", D(2026, 12, 19), D(2026, 12, 20), {
        "te": ["vaikunta_tirumala"], "ta": ["srirangam_vaikunta"]}),
    ("Mandala Pooja", D(2026, 12, 26), D(2026, 12, 27), {"ml": ["ayyappan"]}),
    ("Lohri", D(2027, 1, 12), D(2027, 1, 13), {"pa": ["lohri_dulla_bhatti"]}),
    # before Sankranti: only two rotating slots, and Kerala's Makaravilakku outranks gu/mr Sankranti
    ("Makaravilakku", D(2027, 1, 13), D(2027, 1, 14), {"ml": ["makaravilakku"]}),
    ("Sankranti / Pongal", D(2027, 1, 13), D(2027, 1, 15), {
        "ta": ["pongal"], "te": ["sankranti"], "kn": ["sankranti"], "gu": ["sankranti"], "mr": ["sankranti"]}),
]


def active(day):
    return [e for e in EVENTS if e[1] <= day <= e[2]]


def keys_for(lang, day):
    """Story keys active events want told in `lang` on `day`, in priority order."""
    out = []
    for _, _, _, by_lang in active(day):
        out += [k for k in by_lang.get(lang, []) if k not in out]
    return out


# From 2026-11-28 (owner) Ajab is a Telugu + Tamil channel. Kannada stays only for a live Karnataka event: the
# Mysore records (89k, 28k) were Dasara-day Shorts, while everyday kn Shorts had a median of 10 views. The other
# languages sat at 10-120 views, and ten languages on one channel give the feed no single audience to learn.
# English is the separate Wait, That's Real? channel. Events and trend stories in any other language are ignored.
FOCUS = dt.date(2026, 11, 28)
FOCUS_LANGS = ("te", "ta", "kn", "en")


def in_focus(lang, day):
    if isinstance(day, str):
        day = dt.date.fromisoformat(day)
    return day < FOCUS or lang in FOCUS_LANGS


def langs_for(day):
    """Languages active events want today, in event order (for the rotating slots)."""
    out = []
    for _, _, _, by_lang in active(day):
        out += [l for l in by_lang if l not in out and in_focus(l, day)]
    return out


def reserved(day):
    """Festival stories held back from ordinary picks until their festival (and released once it has passed)."""
    return {k for _, _, last, by_lang in EVENTS if last >= day for ks in by_lang.values() for k in ks}


EXTRA_SLOT = 6          # festival-only evening Short, 13:35 UTC = 19:05 IST (due.py, katha.yml)


def evening_langs(day, done):
    """Languages (not Telugu: slot 3 is its evening) that active events still have an untold story for,
    in event order. `done` = {(key, lang)} posted BEFORE `day`, so every slot that day sees the same list.
    Slot 2 takes the first; the extra slot the second."""
    return [l for l in langs_for(day) if l not in ("te", "en") and any((k, l) not in done for k in keys_for(l, day))]


def extra_slot_on(day, done):
    """The extra festival Short runs when a second language is waiting and it is not a long-form day
    (Sun/Wed: Ajab's quota carries the long-form then). Captions are skipped on these days (make.captions_fit)."""
    return day.weekday() not in (2, 6) and len(evening_langs(day, done)) >= 2
