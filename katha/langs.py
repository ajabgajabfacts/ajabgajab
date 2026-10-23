"""Per-language settings. Adding a language = one entry here (+ its font file).

  whisper  Groq whisper-large-v3 language code for word timings, or None when
           Whisper has no model for it (Odia) -> captions fall back to
           character-proportional timing over the speech span.
           Malayalam too (2026-10-23): on a clean edge-tts voice Whisper dropped a sentence and wrote
           the rest in Gurmukhi, so its asr-match (0.15) only forced a wasted second narration.
  font     file in katha/fonts; wght is applied to variable Noto fonts.
  brand    the channel name in the language's own script (top-left tag).
  audience who the script is written for, given to the writer verbatim.
  edge     Microsoft edge-tts voice used when Gemini TTS's free daily quota is spent
           (None: edge-tts has no Odia/Punjabi voice, so those rely on Gemini).
  sub      fixed "subscribe for more stories" line, on screen at the end, in the description and
           in the auto comment. Fixed rather than written per video so it never drifts or mistranslates.
           Keep it under ~800 px at 48 pt (render shrinks past that; Tamil's 4-word version was 1,387).
  cap      (caption pt, max chars per caption) for Shorts; default (84, 30). Narrow scripts got
           100 pt with a char cap that keeps one line - at 84 Hindi read as a thin strip next to
           Tamil, whose wide glyphs wrap to two lines.
  words    script length. Dravidian languages pack more into each word (agglutinative),
           so the same ~35 s needs far fewer words (Tamil at 103 words ran 55 s).
  channel  (en only) the YouTube channel the language posts to, when it is not Ajab Gajab;
           also its config file for local runs (CI passes CHANNEL_CONFIG).
  voice    storyteller register for the writer prompt; default is the Indian-language one.
"""

LANGS = {
    "hi": dict(cap=(100, 22), sub="और कहानियों के लिए सब्सक्राइब करें", name="Hindi", edge='hi-IN-MadhurNeural', words=(85, 110), whisper="hi", font="Mukta-ExtraBold.ttf", wght=None,
               brand="अजब गजब", audience="Hindi speakers across North and Central India, Tier-2/3 towns and villages; simple spoken Hindustani, not Sanskritised"),
    "mr": dict(cap=(100, 22), sub="आणखी गोष्टींसाठी सबस्क्राइब करा", name="Marathi", edge='mr-IN-ManoharNeural', words=(85, 110), whisper="mr", font="Mukta-ExtraBold.ttf", wght=None,
               brand="अजब गजब", audience="Marathi speakers in Maharashtra; everyday spoken Marathi"),
    "bn": dict(cap=(100, 19), sub="আরও গল্পের জন্য সাবস্ক্রাইব করুন", name="Bengali", edge='bn-IN-BashkarNeural', words=(85, 110), whisper="bn", font="NotoSansBengali.ttf", wght=800,
               brand="আজব গজব", audience="Bengali speakers in West Bengal, Tripura and Assam's Barak valley; everyday spoken Bengali"),
    "ta": dict(sub="சப்ஸ்கிரைப் பண்ணுங்க", name="Tamil", edge='ta-IN-ValluvarNeural', words=(55, 75), whisper="ta", font="NotoSansTamil.ttf", wght=800,
               brand="அஜப் கஜப்", audience="Tamil speakers in Tamil Nadu; everyday spoken Tamil, not literary"),
    "te": dict(cap=(100, 19), sub="మరిన్ని కథలకు సబ్‌స్క్రైబ్ చేయండి", name="Telugu", edge='te-IN-MohanNeural', words=(55, 75), whisper="te", font="NotoSansTelugu.ttf", wght=800,
               brand="అజబ్ గజబ్", audience="Telugu speakers in Andhra Pradesh and Telangana; everyday spoken Telugu"),
    "kn": dict(cap=(100, 19), sub="ಹೆಚ್ಚಿನ ಕಥೆಗಳಿಗೆ ಸಬ್‌ಸ್ಕ್ರೈಬ್ ಮಾಡಿ", name="Kannada", edge='kn-IN-GaganNeural', words=(55, 75), whisper="kn", font="NotoSansKannada.ttf", wght=800,
               brand="ಅಜಬ್ ಗಜಬ್", audience="Kannada speakers in Karnataka; everyday spoken Kannada"),
    "ml": dict(sub="സബ്സ്ക്രൈബ് ചെയ്യൂ", name="Malayalam", edge='ml-IN-MidhunNeural', words=(55, 75), whisper=None, font="NotoSansMalayalam.ttf", wght=800,
               brand="അജബ് ഗജബ്", audience="Malayalam speakers in Kerala; everyday spoken Malayalam"),
    "gu": dict(cap=(100, 21), sub="વધુ વાર્તાઓ માટે સબસ્ક્રાઇબ કરો", name="Gujarati", edge='gu-IN-NiranjanNeural', words=(85, 110), whisper="gu", font="NotoSansGujarati.ttf", wght=800,
               brand="અજબ ગજબ", audience="Gujarati speakers in Gujarat; everyday spoken Gujarati"),
    "or": dict(cap=(100, 19), sub="ଅଧିକ କାହାଣୀ ପାଇଁ ସବସ୍କ୍ରାଇବ କରନ୍ତୁ", name="Odia", edge=None, words=(85, 110), whisper=None, font="NotoSansOriya.ttf", wght=800,
               brand="ଅଜବ ଗଜବ", audience="Odia speakers in Odisha; everyday spoken Odia"),
    "pa": dict(cap=(100, 18), sub="ਹੋਰ ਕਹਾਣੀਆਂ ਲਈ ਸਬਸਕ੍ਰਾਈਬ ਕਰੋ", name="Punjabi", edge=None, words=(85, 110), whisper="pa", font="NotoSansGurmukhi.ttf", wght=800,
               brand="ਅਜਬ ਗਜਬ", audience="Punjabi speakers in Punjab (India); everyday spoken Punjabi in Gurmukhi script"),
    # 2026-10-23: English goes to its own channel, Strange But True (the renamed Money Sorted), not Ajab Gajab.
    "en": dict(sub="Subscribe for more true stories", name="English", edge="en-US-AndrewNeural", words=(80, 100), whisper="en",
               font="Mukta-ExtraBold.ttf", wght=None, brand="Strange But True",
               channel=("Strange But True", "week_test/files/CHANNEL_Money_Sorted_AU_CONFIG.json"),
               voice="Plain, vivid conversational English, like a friend telling the best story they know. No filler, no 'did you know'.",
               audience="English speakers in the US, UK, Canada and Australia who like history and famous places"),
}
