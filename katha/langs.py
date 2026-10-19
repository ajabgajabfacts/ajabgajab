"""Per-language settings. Adding a language = one entry here (+ its font file).

  whisper  Groq whisper-large-v3 language code for word timings, or None when
           Whisper has no model for it (Odia) -> captions fall back to
           character-proportional timing over the speech span.
  font     file in katha/fonts; wght is applied to variable Noto fonts.
  brand    the channel name in the language's own script (top-left tag).
  audience who the script is written for, given to the writer verbatim.
  words    script length. Dravidian languages pack more into each word (agglutinative),
           so the same ~35 s needs far fewer words (Tamil at 103 words ran 55 s).
"""

LANGS = {
    "hi": dict(name="Hindi", words=(85, 110), whisper="hi", font="Mukta-ExtraBold.ttf", wght=None,
               brand="अजब गजब", audience="Hindi speakers across North and Central India, Tier-2/3 towns and villages; simple spoken Hindustani, not Sanskritised"),
    "mr": dict(name="Marathi", words=(85, 110), whisper="mr", font="Mukta-ExtraBold.ttf", wght=None,
               brand="अजब गजब", audience="Marathi speakers in Maharashtra; everyday spoken Marathi"),
    "bn": dict(name="Bengali", words=(85, 110), whisper="bn", font="NotoSansBengali.ttf", wght=800,
               brand="আজব গজব", audience="Bengali speakers in West Bengal, Tripura and Assam's Barak valley; everyday spoken Bengali"),
    "ta": dict(name="Tamil", words=(55, 75), whisper="ta", font="NotoSansTamil.ttf", wght=800,
               brand="அஜப் கஜப்", audience="Tamil speakers in Tamil Nadu; everyday spoken Tamil, not literary"),
    "te": dict(name="Telugu", words=(55, 75), whisper="te", font="NotoSansTelugu.ttf", wght=800,
               brand="అజబ్ గజబ్", audience="Telugu speakers in Andhra Pradesh and Telangana; everyday spoken Telugu"),
    "kn": dict(name="Kannada", words=(55, 75), whisper="kn", font="NotoSansKannada.ttf", wght=800,
               brand="ಅಜಬ್ ಗಜಬ್", audience="Kannada speakers in Karnataka; everyday spoken Kannada"),
    "ml": dict(name="Malayalam", words=(55, 75), whisper="ml", font="NotoSansMalayalam.ttf", wght=800,
               brand="അജബ് ഗജബ്", audience="Malayalam speakers in Kerala; everyday spoken Malayalam"),
    "gu": dict(name="Gujarati", words=(85, 110), whisper="gu", font="NotoSansGujarati.ttf", wght=800,
               brand="અજબ ગજબ", audience="Gujarati speakers in Gujarat; everyday spoken Gujarati"),
    "or": dict(name="Odia", words=(85, 110), whisper=None, font="NotoSansOriya.ttf", wght=800,
               brand="ଅଜବ ଗଜବ", audience="Odia speakers in Odisha; everyday spoken Odia"),
    "pa": dict(name="Punjabi", words=(85, 110), whisper="pa", font="NotoSansGurmukhi.ttf", wght=800,
               brand="ਅਜਬ ਗਜਬ", audience="Punjabi speakers in Punjab (India); everyday spoken Punjabi in Gurmukhi script"),
}
