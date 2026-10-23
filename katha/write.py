"""Script writer + independent fact/language checker."""
import ai

WRITE = """You write viral YouTube {fmt} narration for {audience}.
Language: {lang_name} ONLY, in its native script. Names of people/places in native script too.

STORY SOURCE (English Wikipedia; the ONLY facts you may use):
<<<
{source}
>>>

Write a {lang_name} {fmt} about: {topic_hint}
{angle_line}
SPINE: build the whole story on the ONE most astonishing, specific fact in the source - a physical oddity, an
impossible-seeming feat, an unsolved question, a shocking twist. NOT generic praise, heritage-list status,
"beautiful architecture", district names, distances or administrative detail.

HARD RULES
- {w0}-{w1} words total. {nsent} short spoken sentences. Every sentence must earn its place.
- STRUCTURE (an open loop, the answer withheld until it pays off):
  1. HOOK (sentence 1): the single most astonishing true detail, under 12 words. It SHOULD state the
     astonishing fact; what it withholds is the explanation (how / why / who), which is the reveal.
     No greeting, no "आज हम", no channel name, no "दोस्तों". Start mid-action.
  2. CONTEXT (1-2 sentences): where/when/who, concrete names and numbers from the source.
  3. ESCALATION (2-3 sentences): each adds a stranger detail or a wrong guess; never give away the answer.
  4. REVEAL (second-to-last sentence): the answer/twist, clearly stated - the moment the hook pays off.
  5. {ending_struct}
  Every sentence must follow logically from the one before; a viewer must never feel lost.
- CLEAN: no gore, blood, wounds, torture, corpses described, sexual content or cruelty in detail. Deaths and
  battles are stated plainly in a few words, never graphically. Suitable for a family audience.
- Mythology and legends are framed as what the scripture/legend says ("पुराणों के अनुसार", "मान्यता है"),
  never as historical fact. History and places: only what the source states as fact.
- Respectful toward every deity, faith, community and region. No claims about other religions.
  No miracle/medical/superstition claims stated as true. No politics. No living people.
- NEVER touch disputed religious sites or episodes of temple/mosque destruction, conversion or
  conflict between communities (e.g. Ayodhya, Gyanvapi, Mathura, invasions framed as faith vs faith).
  If the source goes there, leave that part out entirely and tell a different part of the story.
- Make it RELATABLE to this audience: where it fits naturally, connect to their region, festival,
  temple, food or saying - but only with facts the source supports.
- {ending_rule}
- {voice}

Return JSON:
{{"title": "{lang_name} title, max 60 chars, curiosity gap, must be TRUE to the story; name the concrete surprising act (who did what) rather than vague words like secret/mystery",
 "hook_text": "on-screen hook, max 6 words, {lang_name}",
 "kicker": "1-2 word label in {lang_name}, e.g. the equivalent of MYSTERY / TRUE STORY / LEGEND",
 "sentences": ["..."],
 "cta": "max 3 words in {lang_name} meaning 'comment below'",
 "description": "2 short lines in {lang_name}",
 "hashtags": ["5 hashtags without #, mix {lang_name} and English"],
 "visuals": ["3 extra English Wikimedia Commons search phrases for paintings/photos of THIS story"],
 "claims_en": ["every factual claim in the script, in English, one per item"]}}
{feedback}"""

CHECK = """You are a strict fact-checker and native {lang_name} editor.

SOURCE (English Wikipedia):
<<<
{source}
>>>

SCRIPT ({lang_name}):
{script}

CLAIMS (English, as the writer listed them):
{claims}

Check:
1. Every claim in the script is supported by the SOURCE. Legend/scripture content must be framed as legend.
   Numbers, names, dates and places must match the SOURCE exactly.
2. The script is natural, correct {lang_name} in native script (no wrong-script words, no grammar errors
   a native speaker would notice), {w0}-{w1} words, built on one astonishing specific fact (not generic praise), opens with a hook (no greeting), {ending_check}.
3. Structure: hook -> context -> escalation -> reveal -> {ending_name}. The hook is SUPPOSED to state the astonishing
   fact; only the explanation (how/why/who) should wait for the reveal near the end. Do not flag a hook for stating
   the fact itself. Rounded numbers marked "about/around/more than" that stay true to the source are fine; each sentence must follow logically. No graphic violence/gore/blood/sexual detail.
4. Nothing disrespectful to any faith/community, no politics, no living people, no medical/miracle claims as fact.
   REJECT anything touching disputed religious sites or temple/mosque destruction or inter-community conflict.
5. Title and hook are true to the story (no false clickbait).

Return JSON: {{"ok": true/false, "problems": ["specific problem + fix"], "fixed_sentences": [only if ok is false
and the problems are small wording issues: the corrected full sentence list, else []]}}"""


SHORT = dict(fmt="Shorts", nsent="7-9", ending_struct="QUESTION (last sentence): one short question for the comments.",
             ending_rule='Last sentence = one short question viewers answer in the comments (opinion or "had you heard this?").',
             ending_check="ends with a question", ending_name="question")
# A chapter of a long video: deeper, and it lands instead of asking (one question at the very end of the video).
CHAPTER = dict(fmt="long-video chapter", nsent="12-16", ending_struct="LANDING (last sentence): one line that lands the chapter with a sense of wonder - no question, no 'comment'.",
               ending_rule="Last sentence lands the chapter with a sense of wonder. No question, no call to comment or subscribe.",
               ending_check="ends by landing the chapter (no question needed)", ending_name="landing line")


def write(entry, lang, L, source, max_rounds=4, chapter=False):
    """Return (script dict, check dict) or raise if no version passes."""
    feedback = ""
    mode = CHAPTER if chapter else SHORT
    scale = 1.8 if chapter else 1.0
    hint = entry["key"].replace("_", " ")
    for rnd in range(max_rounds):
        w0, w1 = (int(x * scale) for x in L.get("words", (85, 110)))
        voice = L.get("voice") or (f"Natural spoken {L['name']}, like a gripping storyteller at a chai stall. No English "
                                   f"words unless they are everyday in spoken {L['name']}.")
        s = ai.json_call(WRITE.format(audience=L["audience"], lang_name=L["name"], source=source[:14000], voice=voice,
                                      topic_hint=hint, w0=w0, w1=w1, feedback=feedback, **mode,
                                      angle_line=f"ANGLE (build on this): {entry['angle']}" if entry.get("angle") else ""))
        script = "\n".join(s["sentences"])
        c = ai.json_call(CHECK.format(lang_name=L["name"], w0=w0, w1=w1, source=source[:14000], script=script, **mode,
                                      claims="\n".join("- " + x for x in s.get("claims_en", []))),
                         models=ai.CHECK_MODELS, temperature=0.1)
        print(f"[write] round {rnd + 1}: {len(script.split())} words, ok={c.get('ok')} {c.get('problems', [])[:3]}")
        if c.get("ok"):
            return s, c
        if c.get("fixed_sentences") and rnd == max_rounds - 1:
            s["sentences"] = c["fixed_sentences"]
            c2 = ai.json_call(CHECK.format(lang_name=L["name"], w0=w0, w1=w1, **mode, source=source[:14000], script="\n".join(s["sentences"]),
                                           claims="\n".join("- " + x for x in s.get("claims_en", []))), models=ai.CHECK_MODELS, temperature=0.1)
            if c2.get("ok"):
                return s, c2
        feedback = ("\nYour previous draft:\n" + script + "\n\nA checker REJECTED it. EDIT that draft minimally to fix ALL "
                    "of these, changing nothing else:\n" + "\n".join("- " + p for p in c.get("problems", [])))
    raise RuntimeError(f"no script passed the check for {entry['key']}/{lang}")
