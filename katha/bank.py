"""Story bank. Every entry is grounded in its English Wikipedia article(s); the
script is written only from that text and a second model pass rejects anything
the source does not support.

  lang  "all" = pan-Indian story, told in every language
        a code = told only to that language's audience (their region, saint,
                 king, temple). Regional stories are what a viewer relates to,
                 and are preferred over pan-Indian ones 2:1 (see make.pick).
  kind  myth | history | saint | wonder | folk
  art   Wikimedia Commons searches for the visuals, most specific first.

Deliberately left out: living people, figures whose legacy is a live political
or communal fight, and anything that needs a claim about another faith.
Removed 2026-10-19: kashi_vishwanath - its source leads straight into the Gyanvapi
well/demolition history, a live communal and legal dispute.
"""

S = []
def add(key, lang, kind, wiki, art):
    S.append(dict(key=key, lang=lang, kind=kind, wiki=wiki, art=art))

# ── Pan-Indian (told in every language) ─────────────────────────────────────
add("gajendra_moksha", "all", "myth", ["Gajendra Moksha"], ["Gajendra Moksha painting", "Gajendra moksha"])
add("samudra_manthan", "all", "myth", ["Samudra Manthana"], ["Samudra manthan painting", "Churning of the ocean of milk"])
add("dhruva", "all", "myth", ["Dhruva"], ["Dhruva Vishnu painting", "Dhruva Bhagavata"])
add("prahlada_narasimha", "all", "myth", ["Prahlada", "Narasimha"], ["Narasimha Hiranyakashipu painting", "Prahlada painting"])
add("markandeya", "all", "myth", ["Markandeya"], ["Markandeya Shiva Yama painting", "Markandeya"])
add("savitri_satyavan", "all", "myth", ["Savitri and Satyavan"], ["Savitri Satyavan Raja Ravi Varma", "Savitri Yama painting"])
add("ekalavya", "all", "myth", ["Ekalavya"], ["Ekalavya Drona", "Ekalavya painting"])
add("karna_kavacha", "all", "myth", ["Karna"], ["Karna Indra kavacha", "Karna Mahabharata painting"])
add("barbarika", "all", "myth", ["Barbarika"], ["Barbarika", "Khatu Shyam"])
add("bhishma_vow", "all", "myth", ["Bhishma"], ["Bhishma pratigya Raja Ravi Varma", "Bhishma bed of arrows"])
add("abhimanyu", "all", "myth", ["Abhimanyu", "Chakravyuha"], ["Abhimanyu chakravyuha painting", "Abhimanyu Razmnama"])
add("hanuman_sun", "all", "myth", ["Hanuman"], ["Hanuman sun painting", "Hanuman flying painting"])
add("ravana_kailash", "all", "myth", ["Ravananugraha"], ["Ravana lifting Kailash", "Ravananugraha"])
add("ganesha_head", "all", "myth", ["Ganesha"], ["Birth of Ganesha painting", "Shiva Parvati Ganesha painting"])
add("ganesha_scribe", "all", "myth", ["Ganesha", "Vyasa"], ["Vyasa Ganesha Mahabharata", "Ganesha writing"])
add("ganesha_kartikeya_race", "all", "myth", ["Kartikeya", "Ganesha"], ["Ganesha Kartikeya painting", "Shiva family painting"])
add("vamana_bali", "all", "myth", ["Vamana", "Mahabali"], ["Vamana Bali painting", "Trivikrama"])
add("bhagiratha_ganga", "all", "myth", ["Bhagiratha", "Descent of the Ganges"], ["Descent of the Ganges Mahabalipuram", "Shiva Ganga painting"])
add("shakuntala", "all", "myth", ["Shakuntala"], ["Shakuntala Raja Ravi Varma", "Shakuntala painting"])
add("nala_damayanti", "all", "myth", ["Nala and Damayanti"], ["Nala Damayanti painting", "Damayanti Raja Ravi Varma"])
add("ashwatthama", "all", "myth", ["Ashwatthama"], ["Ashwatthama painting", "Ashvatthama Razmnama"])
add("gandhari", "all", "myth", ["Gandhari (Mahabharata)"], ["Gandhari painting", "Gandhari Mahabharata"])
add("yaksha_prashna", "all", "myth", ["Yaksha Prashna"], ["Yudhishthira Yaksha", "Yaksha prashna"])
add("sudama", "all", "myth", ["Sudama"], ["Krishna Sudama painting", "Sudama"])
add("kaliya", "all", "myth", ["Kaliya"], ["Kaliya daman painting", "Krishna Kaliya"])
add("govardhan", "all", "myth", ["Govardhan Hill"], ["Krishna lifting Govardhan painting", "Govardhan"])
add("jatayu", "all", "myth", ["Jatayu"], ["Jatayu Ravana Raja Ravi Varma", "Jatayu painting"])
add("shabari", "all", "myth", ["Shabari"], ["Shabari Rama painting", "Shabari"])
add("kumbhakarna", "all", "myth", ["Kumbhakarna"], ["Kumbhakarna painting", "Kumbhakarna"])
add("parashurama", "all", "myth", ["Parashurama"], ["Parashurama painting", "Parashurama"])
add("nachiketa", "all", "myth", ["Nachiketa"], ["Nachiketa Yama", "Katha Upanishad"])
add("ahilya", "all", "myth", ["Ahalya"], ["Ahalya Rama painting", "Ahalya"])
add("draupadi_akshaya", "all", "myth", ["Akshaya Patra"], ["Draupadi Krishna painting", "Draupadi"])

# ── Hindi belt ──────────────────────────────────────────────────────────────
add("lakshmibai", "hi", "history", ["Rani of Jhansi"], ["Rani of Jhansi painting", "Lakshmibai"])
add("tulsidas", "hi", "saint", ["Tulsidas"], ["Tulsidas painting", "Ramcharitmanas manuscript"])
add("kabir", "hi", "saint", ["Kabir"], ["Kabir painting", "Kabir weaving"])
add("meera", "hi", "saint", ["Meera"], ["Mirabai painting", "Meera bai"])
add("prithviraj_samyukta", "hi", "folk", ["Samyukta (Prithviraj Raso)"], ["Prithviraj Samyukta painting", "Prithviraj Chauhan"])
add("vikram_betal", "hi", "folk", ["Baital Pachisi"], ["Vikram Betal", "Vetala Panchavimshati"])
add("khajuraho", "hi", "wonder", ["Khajuraho Group of Monuments"], ["Kandariya Mahadeva Temple", "Khajuraho temple"])

# ── Marathi ─────────────────────────────────────────────────────────────────
add("shivaji_agra", "mr", "history", ["Shivaji"], ["Shivaji portrait", "Shivaji Maharaj painting"])
add("tanaji_sinhagad", "mr", "history", ["Tanaji Malusare", "Sinhagad"], ["Sinhagad fort", "Tanaji Malusare"])
add("tukaram", "mr", "saint", ["Tukaram"], ["Tukaram painting", "Sant Tukaram"])
add("dnyaneshwar", "mr", "saint", ["Dnyaneshwar"], ["Dnyaneshwar painting", "Sant Dnyaneshwar wall"])
add("vitthal_pandharpur", "mr", "myth", ["Vithoba", "Pundalik"], ["Vithoba painting", "Pandharpur Vitthal"])
add("ahilyabai", "mr", "history", ["Ahilyabai Holkar"], ["Ahilyabai Holkar painting", "Ahilyabai Holkar"])
add("ajanta_ellora", "mr", "wonder", ["Kailasa temple, Ellora"], ["Kailasa temple Ellora", "Ellora Caves"])

# ── Bengali ─────────────────────────────────────────────────────────────────
add("behula", "bn", "folk", ["Behula", "Manasamangal Kavya"], ["Behula Lakhindar", "Manasa goddess painting"])
add("mahishasura", "bn", "myth", ["Mahishasura Mardini", "Durga Puja"], ["Durga Mahishasura painting", "Kalighat painting Durga"])
add("chaitanya", "bn", "saint", ["Chaitanya Mahaprabhu"], ["Chaitanya Mahaprabhu painting", "Chaitanya sankirtan"])
add("ramakrishna_kali", "bn", "saint", ["Ramakrishna", "Dakshineswar Kali Temple"], ["Dakshineswar Kali Temple", "Ramakrishna Paramahamsa"])
add("rani_rashmoni", "bn", "history", ["Rani Rashmoni"], ["Rani Rashmoni", "Dakshineswar temple 19th century"])
add("gopal_bhar", "bn", "folk", ["Gopal Bhar", "Krishnachandra Roy"], ["Krishnanagar Rajbari", "Krishnachandra Roy"])
add("bishnupur", "bn", "wonder", ["Bishnupur, Bankura"], ["Bishnupur terracotta temple", "Rasmancha Bishnupur"])

# ── Tamil ───────────────────────────────────────────────────────────────────
add("kannagi", "ta", "folk", ["Kannagi", "Silappatikaram"], ["Kannagi statue Chennai", "Kannagi painting"])
add("raja_raja_temple", "ta", "wonder", ["Brihadisvara Temple, Thanjavur", "Rajaraja I"], ["Brihadeeswarar Temple Thanjavur", "Rajaraja Chola"])
add("murugan_fruit", "ta", "myth", ["Kartikeya", "Palani Murugan Temple"], ["Murugan painting", "Palani temple"])
add("andal", "ta", "saint", ["Andal"], ["Andal painting", "Srivilliputhur Andal temple"])
add("karikala_kallanai", "ta", "history", ["Kallanai", "Karikala Chola"], ["Kallanai dam", "Karikala Chola"])
add("thiruvalluvar", "ta", "saint", ["Valluvar"], ["Thiruvalluvar statue Kanyakumari", "Valluvar"])
add("meenakshi", "ta", "myth", ["Meenakshi", "Meenakshi Temple"], ["Meenakshi Amman Temple", "Meenakshi Sundareswarar wedding painting"])

# ── Telugu ──────────────────────────────────────────────────────────────────
add("venkateswara_loan", "te", "myth", ["Venkateswara", "Padmavati (goddess)"], ["Venkateswara painting", "Tirumala temple"])
add("kannappa", "te", "saint", ["Kannappa Nayanar", "Srikalahasti Temple"], ["Kannappa Nayanar", "Srikalahasti temple"])
add("annamacharya", "te", "saint", ["Annamacharya"], ["Annamacharya statue", "Annamayya"])
add("krishnadevaraya", "te", "history", ["Krishnadevaraya"], ["Krishnadevaraya statue", "Vijayanagara Hampi"])
add("tenali_rama", "te", "folk", ["Tenali Ramakrishna"], ["Tenali Ramakrishna", "Tenali Rama"])
add("rudramadevi", "te", "history", ["Rudrama Devi"], ["Rudrama Devi", "Warangal Fort"])
add("ramappa", "te", "wonder", ["Ramappa Temple"], ["Ramappa Temple", "Ramappa temple sculpture"])

# ── Kannada ─────────────────────────────────────────────────────────────────
add("chamundeshwari", "kn", "myth", ["Chamundeshwari Temple", "Mahishasura"], ["Chamundi Hills temple", "Chamundeshwari"])
add("kittur_chennamma", "kn", "history", ["Kittur Chennamma"], ["Kittur Chennamma statue", "Kittur fort"])
add("basavanna", "kn", "saint", ["Basava"], ["Basavanna statue", "Basaveshwara"])
add("hampi", "kn", "wonder", ["Hampi", "Vittala Temple"], ["Vittala temple stone chariot", "Hampi ruins"])
add("gommateshwara", "kn", "wonder", ["Gommateshwara statue", "Bahubali"], ["Gommateshwara statue Shravanabelagola", "Bahubali statue"])
add("onake_obavva", "kn", "history", ["Onake Obavva", "Chitradurga Fort"], ["Chitradurga Fort", "Onake Obavva"])

# ── Malayalam ───────────────────────────────────────────────────────────────
add("mahabali_onam", "ml", "myth", ["Mahabali", "Onam"], ["Mahabali Onam", "Vamana Mahabali painting"])
add("parashurama_kerala", "ml", "myth", ["Parashurama", "Kerala"], ["Parashurama axe Kerala", "Parashurama painting"])
add("ayyappan", "ml", "myth", ["Ayyappan", "Sabarimala"], ["Ayyappan painting", "Sabarimala temple"])
add("guruvayurappan", "ml", "myth", ["Guruvayur Temple"], ["Guruvayur temple", "Guruvayurappan"])
add("adi_shankara", "ml", "saint", ["Adi Shankara"], ["Adi Shankara painting", "Kalady"])
add("marthanda_varma", "ml", "history", ["Marthanda Varma", "Battle of Colachel"], ["Marthanda Varma", "Padmanabhapuram Palace"])
add("padmanabhaswamy", "ml", "wonder", ["Padmanabhaswamy Temple"], ["Padmanabhaswamy Temple", "Anantha Padmanabha painting"])

# ── Gujarati ────────────────────────────────────────────────────────────────
add("dwarka", "gu", "myth", ["Dwarka", "Dwarakadhish Temple"], ["Dwarkadhish temple", "Dwarka Krishna painting"])
add("somnath", "gu", "wonder", ["Somnath temple"], ["Somnath temple", "Somnath"])
add("narsinh_mehta", "gu", "saint", ["Narsinh Mehta"], ["Narsinh Mehta", "Narsinh Mehta statue"])
add("rani_ki_vav", "gu", "wonder", ["Rani ki vav"], ["Rani ki vav", "Rani ki vav sculpture"])
add("modhera", "gu", "wonder", ["Modhera Sun Temple"], ["Modhera Sun Temple", "Modhera surya kund"])
add("jalaram", "gu", "saint", ["Jalaram Bapa"], ["Jalaram Bapa", "Virpur Jalaram temple"])

# ── Odia ────────────────────────────────────────────────────────────────────
add("jagannath_wood", "or", "myth", ["Jagannath", "Nabakalebara"], ["Jagannath Puri painting", "Jagannath Balabhadra Subhadra pattachitra"])
add("konark", "or", "wonder", ["Konark Sun Temple"], ["Konark Sun Temple wheel", "Konark Sun Temple"])
add("rath_yatra", "or", "myth", ["Ratha Yatra (Puri)"], ["Rath Yatra Puri", "Ratha Yatra chariot Puri"])
add("kharavela", "or", "history", ["Kharavela", "Hathigumpha inscription"], ["Hathigumpha inscription", "Udayagiri Khandagiri caves"])
add("jayadeva", "or", "saint", ["Jayadeva", "Gita Govinda"], ["Gita Govinda painting", "Jayadeva"])
add("kalinga_ashoka", "or", "history", ["Kalinga War", "Dhauli"], ["Dhauli Shanti Stupa", "Ashoka edicts Dhauli"])

# ── Punjabi (folk, deliberately not religious) ──────────────────────────────
add("heer_ranjha", "pa", "folk", ["Heer Ranjha"], ["Heer Ranjha painting", "Heer Ranjha"])
add("sohni_mahiwal", "pa", "folk", ["Sohni Mahiwal"], ["Sohni Mahiwal painting", "Sohni Mahiwal"])
add("mirza_sahiban", "pa", "folk", ["Mirza Sahiban"], ["Mirza Sahiban", "Mirza Sahiban painting"])
add("bhagat_puran", "pa", "folk", ["Puran Bhagat"], ["Puran Bhagat", "Puran Bhagat painting"])
add("dulla_bhatti", "pa", "folk", ["Dulla Bhatti", "Lohri"], ["Lohri bonfire", "Dulla Bhatti"])

# ── Ajab Gajab: real, verifiable "that can't be true" places and events ─────
# The scroll-stoppers. Each is told to the audience of its own region (and the
# pan-Indian ones in every language). Legends are framed AS legends.
add("roopkund", "all", "wonder", ["Roopkund"], ["Roopkund lake skeletons", "Roopkund"])
add("shani_shingnapur", "mr", "wonder", ["Shani Shingnapur"], ["Shani Shingnapur", "Shani Shingnapur temple"])
add("shetpal", "mr", "wonder", ["Shetphal"], ["Shetphal village", "Indian cobra"])
add("lonar", "mr", "wonder", ["Lonar Lake"], ["Lonar crater lake", "Lonar Lake"])
add("kuldhara", "hi", "folk", ["Kuldhara"], ["Kuldhara abandoned village", "Kuldhara"])
add("bhangarh", "hi", "folk", ["Bhangarh Fort"], ["Bhangarh Fort", "Bhangarh ruins"])
add("karni_mata", "hi", "wonder", ["Karni Mata Temple"], ["Karni Mata Temple rats", "Karni Mata temple Deshnoke"])
add("chand_baori", "hi", "wonder", ["Chand Baori"], ["Chand Baori stepwell", "Chand Baori"])
add("kongthong", "all", "wonder", ["Kongthong"], ["Kongthong village Meghalaya", "Meghalaya village"])
add("root_bridges", "all", "wonder", ["Living root bridge"], ["Living root bridge Meghalaya", "Double decker root bridge"])
add("loktak", "all", "wonder", ["Loktak Lake", "Keibul Lamjao National Park"], ["Loktak Lake phumdi", "Sangai deer"])
add("jatinga", "bn", "wonder", ["Jatinga"], ["Jatinga Assam", "Dima Hasao hills"])
add("majuli", "bn", "wonder", ["Majuli"], ["Majuli island", "Majuli satra"])
add("kodinhi", "ml", "wonder", ["Kodinhi"], ["Kodinhi village", "Malappuram"])
add("mattur", "kn", "wonder", ["Mattur"], ["Mattur village", "Shimoga Tunga river"])
add("lepakshi", "te", "wonder", ["Veerabhadra Temple, Lepakshi", "Lepakshi"], ["Lepakshi hanging pillar", "Lepakshi temple Nandi"])
add("belum_caves", "te", "wonder", ["Belum Caves"], ["Belum Caves", "Belum caves stalactites"])
add("kailasa_monolith", "all", "wonder", ["Kailasa temple, Ellora"], ["Kailasa temple Ellora aerial", "Kailasa temple Ellora"])
add("iron_pillar", "all", "wonder", ["Iron pillar of Delhi"], ["Iron pillar Delhi", "Qutb complex iron pillar"])
add("thanjavur_shadow", "ta", "wonder", ["Brihadisvara Temple, Thanjavur"], ["Brihadeeswarar vimana", "Thanjavur temple tower"])
add("chilika", "or", "wonder", ["Chilika Lake", "Irrawaddy dolphin"], ["Chilika Lake", "Irrawaddy dolphin Chilika"])
add("golden_temple_langar", "pa", "wonder", ["Langar (Sikhism)", "Golden Temple"], ["Golden Temple langar kitchen", "Harmandir Sahib"])
add("rani_ki_vav_lost", "gu", "wonder", ["Rani ki vav"], ["Rani ki vav steps", "Rani ki vav"])
add("dholavira", "gu", "history", ["Dholavira"], ["Dholavira ruins", "Dholavira signboard"])
add("sundarbans_tiger", "bn", "wonder", ["Sundarbans", "Bonbibi"], ["Sundarbans tiger", "Sundarbans mangrove"])

# ── Scout-driven (2026-10-19): what the measured winners are made of ────────
# Fact Show (51k subs, median 569k): a famous temple's "biggest secret".
# The Sacred Thread (43k, 470k) / Priyansh Shukla / hindufactt: the gods' families and "what happened next".
# Dharma_diaries (525k, 160k): "what happened AFTER" a famous episode.
# MARATHI SANATANI FACTS (589k, 361k): Vitthal/Pandharpur saints. Checker still rejects anything the
# source does not support, so popular temple myths (flag against the wind etc.) cannot slip in.
add("riddhi_siddhi", "all", "myth", ["Riddhi and Siddhi", "Ganesha"], ["Ganesha Riddhi Siddhi painting", "Ganesha with consorts"])
add("kartikeya_wives", "all", "myth", ["Devasena", "Valli (goddess)"], ["Murugan Valli Devasena painting", "Kartikeya consorts"])
add("prahlad_after", "all", "myth", ["Prahlada"], ["Prahlada Narasimha painting", "Narasimha blessing Prahlada"])
add("samba_pestle", "all", "myth", ["Samba (Krishna's son)", "Mausala Parva"], ["Samba Krishna son", "Dwarka submerged painting"])
add("garuda_vishnu", "all", "myth", ["Garuda"], ["Garuda Vishnu painting", "Garuda amrita"])
add("alakshmi", "all", "myth", ["Alakshmi"], ["Lakshmi painting Raja Ravi Varma", "Lakshmi lotus painting"])
add("hanuman_son", "all", "myth", ["Makardhwaja"], ["Makardhwaja Hanuman", "Hanuman painting"])
add("shiva_ganga_jata", "all", "myth", ["Ganga in Hinduism"], ["Shiva Ganga jata painting", "Descent of Ganga painting"])
add("karna_after", "all", "myth", ["Karna", "Vrishaketu"], ["Karna death painting Mahabharata", "Karna chariot wheel painting"])
add("krishna_last_day", "all", "myth", ["Death of Krishna", "Jara (hunter)"], ["Krishna Jara hunter painting", "Krishna under tree painting"])
add("jagannath_secret", "or", "myth", ["Jagannath Temple, Puri", "Nabakalebara"], ["Jagannath Temple Puri", "Jagannath pattachitra"])
add("kanhopatra", "mr", "saint", ["Kanhopatra"], ["Kanhopatra samadhi Pandharpur", "Vithoba Pandharpur"])
add("kali_dakshineswar", "bn", "myth", ["Dakshineswar Kali Temple", "Bhavatarini"], ["Dakshineswar Kali Temple", "Kali painting Kalighat"])
add("tirupati_hair", "te", "myth", ["Venkateswara Temple, Tirumala", "Neela Devi"], ["Tirumala temple gopuram", "Venkateswara painting"])
add("sabarimala_pathinettam", "ml", "myth", ["Sabarimala", "Ayyappan"], ["Sabarimala temple", "Ayyappan painting"])
add("palani_bhogar", "ta", "saint", ["Bogar", "Palani Murugan Temple"], ["Palani hill temple", "Bogar siddhar"])


# ── Angles: the one astonishing fact a story must be built on ───────────────
# Without one the writer drifts to safe filler (Lepakshi came back about murals and
# UNESCO lists instead of the hanging pillar). The checker still verifies it.
ANGLES = {
    "lepakshi": "the hanging pillar that does not fully rest on the floor",
    "konark": "the temple is built as a giant stone chariot and its carved wheels work as sundials",
    "iron_pillar": "a 1,600-year-old iron pillar that has barely rusted",
    "root_bridges": "bridges grown, not built, from living tree roots",
    "kongthong": "every villager has their own tune that works as their name",
    "kodinhi": "a village with an unusually high number of twins",
    "jatinga": "birds that fly towards lights on foggy nights",
    "shani_shingnapur": "a village whose houses traditionally have no doors",
    "mattur": "a village where people speak Sanskrit in daily life",
    "karni_mata": "a temple where thousands of rats are revered",
    "lonar": "a lake inside a crater made by a meteorite",
    "loktak": "floating islands and the world's only floating national park",
    "chand_baori": "a stepwell with thousands of steps going deep underground",
    "belum_caves": "one of the longest cave systems in the Indian subcontinent",
    "thanjavur_shadow": "how a 1,000-year-old granite tower this tall was built",
    "roopkund": "a Himalayan lake full of ancient human remains (no graphic detail)",
    "kailasa_monolith": "a whole temple carved top-down from a single rock",
    "rani_ki_vav": "a stepwell buried by floods for centuries and rediscovered",
    "kuldhara": "an entire village abandoned overnight - framed as legend vs what is known",
    "bhangarh": "the curse legend attached to the fort - framed as legend, with what the source says",
    "majuli": "one of the world's largest river islands, shrinking every year",
    "chilika": "Asia's largest brackish lagoon and its rare dolphins",
    "golden_temple_langar": "a free kitchen that feeds huge numbers of people every day",
    "dholavira": "a 4,500-year-old city with advanced water management and a signboard",
    "sundarbans_tiger": "tigers that swim, and the forest goddess Bonbibi",
    "gommateshwara": "a 57-foot statue carved from a single rock over 1,000 years ago",
    "hampi": "the stone chariot and musical pillars of a lost capital",
    "ramappa": "a temple named after its sculptor, built with bricks light enough to float",
    "modhera": "a sun temple designed around sunlight on the equinox",
    "padmanabhaswamy": "the vaults and the treasure found inside",
}
for _s in S:
    _s["angle"] = ANGLES.get(_s["key"], "")

# ── Beyond history (2026-10-19, owner: "do not restrict ourselves to history") ─
# science | nature | animal | space | engineering | food | sport | record | people
# Same rules: Wikipedia-grounded, no living people, family-clean. `angle` is the spine.
def add2(key, lang, kind, wiki, art, angle):
    add(key, lang, kind, wiki, art); ANGLES[key] = angle; S[-1]["angle"] = angle

# Space & science (pan-Indian)
add2("chandrayaan3", "all", "space", ["Chandrayaan-3"], ["Chandrayaan-3 Vikram lander", "Chandrayaan-3 launch"], "the first landing near the Moon's south pole")
add2("mangalyaan", "all", "space", ["Mars Orbiter Mission"], ["Mars Orbiter Mission spacecraft", "Mars Orbiter Mission launch PSLV"], "reaching Mars on the first attempt, on a tiny budget")
add2("aryabhata_sat", "all", "space", ["Aryabhata (satellite)"], ["Aryabhata satellite", "Aryabhata satellite stamp"], "India's first satellite and how it got to space")
add2("ramanujan", "all", "people", ["Srinivasa Ramanujan"], ["Srinivasa Ramanujan", "Ramanujan Trinity College"], "a self-taught clerk whose letter stunned Cambridge")
add2("raman_effect", "all", "science", ["C. V. Raman", "Raman scattering"], ["C. V. Raman", "Raman spectroscopy"], "a Nobel Prize from a question about why the sea is blue")
add2("zero", "all", "science", ["0", "Brahmagupta"], ["Brahmagupta", "Bakhshali manuscript"], "how India gave the world zero as a number")
add2("bakhshali", "all", "science", ["Bakhshali manuscript"], ["Bakhshali manuscript", "Bakhshali manuscript zero"], "the oldest surviving written zero, found in a field")
add2("sushruta", "all", "science", ["Sushruta Samhita"], ["Sushruta statue", "Sushruta Samhita manuscript"], "an ancient text describing plastic surgery of the nose")
# Nature & animals
add2("mawsynram", "all", "nature", ["Mawsynram"], ["Mawsynram", "Meghalaya clouds"], "one of the wettest places on Earth")
add2("amur_falcon", "all", "animal", ["Amur falcon"], ["Amur falcon", "Amur falcon Nagaland"], "a tiny falcon that flies non-stop across an ocean to Africa")
add2("king_cobra", "all", "animal", ["King cobra"], ["King cobra", "King cobra Ophiophagus"], "the only snake that builds a nest")
add2("gir_lions", "gu", "animal", ["Asiatic lion", "Gir National Park"], ["Asiatic lion Gir", "Gir National Park lion"], "the last wild Asiatic lions on Earth live only in Gujarat")
add2("olive_ridley", "or", "animal", ["Olive ridley sea turtle", "Gahirmatha Marine Wildlife Sanctuary"], ["Olive ridley arribada", "Olive ridley sea turtle"], "hundreds of thousands of turtles arriving on one beach at once")
add2("nilgiri_tahr", "ta", "animal", ["Nilgiri tahr"], ["Nilgiri tahr", "Eravikulam Nilgiri tahr"], "Tamil Nadu's state animal that lives on sheer cliffs")
add2("neelakurinji", "ml", "nature", ["Strobilanthes kunthiana"], ["Neelakurinji", "Neelakurinji Munnar"], "a flower that blooms only once in twelve years")
add2("jog_falls", "kn", "nature", ["Jog Falls"], ["Jog Falls", "Jog Falls monsoon"], "one of India's highest plunge waterfalls")
add2("sundarbans_mangrove", "bn", "nature", ["Sundarbans"], ["Sundarbans mangrove", "Sundarbans Royal Bengal tiger"], "the largest mangrove forest in the world")
add2("kaziranga_rhino", "bn", "animal", ["Kaziranga National Park", "Indian rhinoceros"], ["Kaziranga rhinoceros", "Indian rhinoceros"], "two-thirds of the world's one-horned rhinos live in one park")
add2("blackbuck", "pa", "animal", ["Blackbuck"], ["Blackbuck", "Blackbuck running"], "one of the fastest animals on land")
add2("lonar_salt", "mr", "nature", ["Lonar Lake"], ["Lonar lake pink", "Lonar crater"], "the crater lake that turned pink overnight in 2020")
# Engineering & records
add2("pamban_bridge", "ta", "engineering", ["Pamban Bridge"], ["Pamban Bridge", "Pamban rail bridge"], "a sea bridge that lifts open for ships")
add2("chenab_bridge", "all", "engineering", ["Chenab Rail Bridge"], ["Chenab Rail Bridge", "Chenab bridge arch"], "the world's highest railway arch bridge")
add2("atal_tunnel", "all", "engineering", ["Atal Tunnel"], ["Atal Tunnel", "Atal Tunnel Rohtang"], "the world's longest highway tunnel above 10,000 feet")
add2("statue_unity", "gu", "engineering", ["Statue of Unity"], ["Statue of Unity", "Statue of Unity Narmada"], "the tallest statue in the world")
add2("howrah_bridge", "bn", "engineering", ["Howrah Bridge"], ["Howrah Bridge", "Howrah Bridge night"], "a giant bridge built without a single nut or bolt")
add2("dabbawala", "mr", "record", ["Dabbawala"], ["Mumbai dabbawala", "Dabbawala lunch boxes"], "a lunchbox delivery system with almost no mistakes")
add2("konkan_railway", "mr", "engineering", ["Konkan Railway"], ["Konkan Railway tunnel", "Konkan Railway bridge"], "a railway through 2,000 bridges and 90 tunnels")
add2("golconda_diamonds", "te", "history", ["Golconda", "Koh-i-Noor"], ["Golconda fort", "Golconda Fort clapping portico"], "the fort whose mines gave the world the Koh-i-Noor")
add2("charminar", "te", "engineering", ["Charminar"], ["Charminar", "Charminar night"], "why a 400-year-old monument was built in the middle of a city")
add2("mysore_palace", "kn", "engineering", ["Mysore Palace"], ["Mysore Palace illuminated", "Mysore Palace"], "a palace lit by nearly 100,000 bulbs")
# 2026-10-23: Mysore Palace (the 1897 fire during a royal wedding) hit 14.3k views, ~10x the next best.
# More of that shape: a landmark Kannada viewers know, plus a dramatic true event at it.
add2("mysore_dasara", "kn", "history", ["Mysore Dasara"], ["Mysore Dasara Jamboo Savari", "Mysore Dasara elephant"], "the elephant that carries a golden howdah through Mysore")
add2("shivanasamudra", "kn", "engineering", ["Shivanasamudra Falls"], ["Shivanasamudra Falls", "Shivanasamudra hydroelectric"], "the waterfall that powered one of Asia's first hydroelectric stations")
add2("krs_dam", "kn", "engineering", ["Krishna Raja Sagara", "M. Visvesvaraya"], ["Krishna Raja Sagara dam", "Brindavan Gardens"], "the dam built with Visvesvaraya's automatic gates")
add2("belur_temple", "kn", "wonder", ["Chennakeshava Temple, Belur"], ["Chennakeshava Temple Belur", "Belur temple carvings"], "a temple that took 103 years to finish")
add2("gol_gumbaz", "kn", "engineering", ["Gol Gumbaz"], ["Gol Gumbaz", "Gol Gumbaz whispering gallery"], "a dome where a whisper carries across the hall")
add2("badami_caves", "kn", "wonder", ["Badami cave temples"], ["Badami cave temples", "Badami cave temple carving"], "temples cut straight into a sandstone cliff 1,400 years ago")
add2("vembanad_boat", "ml", "sport", ["Nehru Trophy Boat Race", "Chundan vallam"], ["Snake boat race Kerala", "Nehru Trophy Boat Race"], "snake boats over 100 feet long rowed by 100 people")
# Food origins
add2("biryani", "all", "food", ["Biryani"], ["Hyderabadi biryani", "Biryani"], "how biryani travelled and changed across India")
add2("chai_india", "all", "food", ["Masala chai"], ["Masala chai", "Assam tea garden"], "chai only became India's drink in the 20th century")
add2("rasgulla", "or", "food", ["Rasgulla"], ["Rasgulla", "Pahala rasagola"], "the sweet that Odisha and Bengal both claim")
add2("mysore_pak", "kn", "food", ["Mysore pak"], ["Mysore pak", "Mysore pak sweet"], "a sweet invented in a palace kitchen")
# 2026-10-26: Kannada is slot 0 every day (make.KN_DAILY), so the kn bank needed depth. Same shape as
# Mysore Palace: a Karnataka place or person plus one striking true event. Each angle was found in its
# article's text before adding. Left out: Akka Mahadevi (Lingayat-religion dispute) and Kanaka Dasa's
# Udupi window (live caste dispute over the Kanakana Kindi).
add2("gokarna_atmalinga", "kn", "myth", ["Gokarna, Karnataka"], ["Mahabaleshwar Temple Gokarna", "Gokarna"], "Ravana carried Shiva's Atmalinga home to Lanka, and Ganesha tricked him into setting it down at Gokarna")
add2("talakadu_curse", "kn", "history", ["Talakadu"], ["Talakadu temple sand", "Talakadu"], "a temple town of over 30 temples, most now buried in sand, and the curse of Rani Alamelamma")
add2("purandara_dasa", "kn", "saint", ["Purandara Dasa"], ["Purandara Dasa", "Purandara Dasa statue"], "a rich jewel merchant who gave everything away and became the grandsire of Carnatic music")
add2("rani_abbakka", "kn", "history", ["Abbakka Chowta"], ["Abbakka", "Rani Abbakka", "Ullal"], "the Tulu queen of Ullal who fought the Portuguese, remembered as Abhaya Rani, the fearless queen")
add2("sangolli_rayanna", "kn", "history", ["Sangolli Rayanna", "Kittur Chennamma"], ["Sangolli Rayanna statue", "Sangolli Rayanna"], "Kittur's commander who kept fighting the British after Kittur fell, until he was hanged in 1831")
add2("halebidu", "kn", "wonder", ["Hoysaleswara Temple"], ["Hoysaleswara Temple Halebidu", "Halebidu carvings"], "a 12th-century soapstone temple whose friezes are a picture-book of life 900 years ago")
add2("somanathapura", "kn", "wonder", ["Chennakeshava Temple, Somanathapura"], ["Somanathapura temple", "Somanathapura Keshava temple"], "a temple on a star-shaped platform with three identical sanctums")
add2("pattadakal", "kn", "wonder", ["Pattadakal"], ["Pattadakal temples", "Virupaksha temple Pattadakal"], "north Indian and south Indian temple styles built side by side, and one temple that fuses both")
add2("aihole", "kn", "wonder", ["Aihole"], ["Durga temple Aihole", "Aihole temples"], "the village where builders experimented with 16 types of temples, the cradle of temple architecture")
add2("murudeshwar", "kn", "wonder", ["Murdeshwar"], ["Murudeshwar Shiva statue", "Murudeshwar temple"], "one of the world's tallest Shiva statues, on the Arabian Sea shore")
add2("st_marys_islands", "kn", "nature", ["St. Mary's Islands"], ["St. Mary's Island basalt columns", "St. Mary's Islands Udupi"], "islands of basalt columns formed over 90 million years ago, where Vasco da Gama landed in 1498")
add2("talakaveri", "kn", "myth", ["Talakaveri"], ["Talakaveri", "Bhagamandala"], "the spring on the Brahmagiri hills where the Kaveri river is born")
add2("ranganathittu", "kn", "animal", ["Ranganathittu Bird Sanctuary"], ["Ranganathittu Bird Sanctuary", "Ranganathittu birds"], "river islets that became a bird sanctuary after Salim Ali persuaded the king of Mysore")
add2("kempegowda", "kn", "history", ["Kempe Gowda I"], ["Kempe Gowda statue", "Kempegowda tower"], "the Vijayanagara governor who built Bengaluru's fort and town in 1537")
add2("lalbagh_glasshouse", "kn", "engineering", ["Lal Bagh"], ["Lalbagh Glass House", "Lalbagh"], "a glass house modelled on London's Crystal Palace, built with cast iron from Glasgow")
add2("vidhana_soudha", "kn", "engineering", ["Vidhana Soudha"], ["Vidhana Soudha", "Vidhana Soudha night"], "the largest state legislature building in India")
add2("mysore_sandal_soap", "kn", "history", ["Mysore Sandal Soap"], ["Mysore Sandal Soap", "Sandalwood"], "a king opened a soap factory in 1916 because the First World War left Mysore's sandalwood unsold")
add2("bull_temple", "kn", "folk", ["Dodda Basavana Gudi"], ["Dodda Basavana Gudi Nandi", "Bull Temple Bangalore"], "a giant Nandi in Bengaluru and the groundnut fair held for it every year")
add2("bengaluru_karaga", "kn", "folk", ["Bangalore Karaga"], ["Bengaluru Karaga", "Karaga festival"], "Bengaluru's old festival for Draupadi, worshipped as a form of Adishakti")
add2("channapatna_toys", "kn", "folk", ["Channapatna toys"], ["Channapatna toys", "Channapatna wooden toys"], "Karnataka's toy town, where toys are lacquered from ivory-wood")
add2("yakshagana", "kn", "folk", ["Yakshagana"], ["Yakshagana", "Yakshagana performer"], "a theatre of gods and demons performed through the whole night")
add2("kambala", "kn", "sport", ["Kambala"], ["Kambala buffalo race", "Kambala"], "buffalo races run through slushy paddy fields")
add2("mayurasharma", "kn", "history", ["Mayuravarma"], ["Talagunda inscription", "Kadamba dynasty"], "a scholar humiliated by a guard at Kanchi who left his studies and founded his own kingdom")
add2("pulakeshin", "kn", "history", ["Pulakeshin II"], ["Pulakeshin II", "Badami fort"], "the Chalukya king who stopped the mighty northern emperor Harsha")
add2("kuvempu", "kn", "people", ["Kuvempu"], ["Kuvempu", "Kuppali"], "the poet who won Kannada its first Jnanpith Award")
add2("dr_rajkumar", "kn", "people", ["Dr. Rajkumar"], ["Rajkumar actor", "Dr. Rajkumar"], "Kannada cinema's legend, whose last wish was that his eyes be donated")
add2("shakuntala_devi", "kn", "people", ["Shakuntala Devi"], ["Shakuntala Devi"], "the 'Human Computer' whose Guinness record was only certified 40 years later")
add2("vada_pav", "mr", "food", ["Vada pav"], ["Vada pav", "Vada pav Mumbai"], "the snack invented outside a Mumbai railway station")
add2("idli", "ta", "food", ["Idli"], ["Idli", "Idli sambar"], "where the idli really came from")
add2("hyderabadi_haleem", "te", "food", ["Haleem"], ["Hyderabadi haleem", "Haleem"], "the first Indian dish with a GI tag for a meat dish")
add2("langar_food", "pa", "food", ["Langar (Sikhism)"], ["Langar kitchen", "Langar Amritsar"], "a kitchen that feeds everyone for free, every day")
# Sport legends (deceased only)
add2("dhyan_chand", "all", "sport", ["Dhyan Chand"], ["Dhyan Chand", "Dhyan Chand statue"], "the hockey wizard whose stick was broken open to check for a magnet")
add2("milkha_singh", "pa", "sport", ["Milkha Singh"], ["Milkha Singh", "Milkha Singh 1960 Rome"], "the Flying Sikh and the race he lost by a fraction")
add2("kd_jadhav", "mr", "sport", ["Khashaba Dadasaheb Jadhav"], ["Khashaba Dadasaheb Jadhav", "Khashaba Jadhav statue"], "independent India's first individual Olympic medal")
add2("chuni_goswami", "bn", "sport", ["Chuni Goswami"], ["Chuni Goswami", "Mohun Bagan"], "a footballer who also played first-class cricket")
add2("kalam", "ta", "people", ["A. P. J. Abdul Kalam"], ["A. P. J. Abdul Kalam", "Kalam Rameswaram house"], "from selling newspapers in Rameswaram to President")
add2("tagore_anthems", "bn", "people", ["Rabindranath Tagore"], ["Rabindranath Tagore", "Tagore painting"], "one poet wrote the national anthems of two countries")
add2("satyajit_ray", "bn", "people", ["Satyajit Ray"], ["Satyajit Ray", "Pather Panchali"], "an honorary Oscar delivered to his hospital bed")
# Telugu devotees (2026-10-20): Kannappa in Telugu (mPah9AIzlXM) out-drew every other post; more of the same
# kind. Each angle was checked against its article before adding.
add2("ramadasu", "te", "saint", ["Bhadrachala Ramadasu"], ["Bhadrachalam temple", "Bhadrachala Ramadasu"], "he built the Bhadrachalam temple with tax money and was jailed until it was repaid; legend says Rama and Lakshmana paid it")
add2("simhachalam_chandanam", "te", "wonder", ["Varaha Lakshmi Narasimha temple, Simhachalam"], ["Simhachalam temple", "Simhachalam gopuram"], "a deity kept under sandalwood paste all year, seen in its true form for only 12 hours")
add2("pothana", "te", "saint", ["Pothana"], ["Bammera Pothana", "Pothana statue"], "the poet who refused to dedicate his Bhagavatam to the king and gave it to Rama")
add2("molla", "te", "saint", ["Atukuri Molla"], ["Atukuri Molla statue", "Molla Ramayanam"], "a potter's daughter who wrote a Telugu Ramayana and would not dedicate it to any king")
add2("tyagaraja_nidhi", "te", "saint", ["Tyagaraja"], ["Tyagaraja", "Thiruvaiyaru Tyagaraja"], "he turned down a king's wealth with a song asking 'does wealth bring happiness?'")
add2("vengamamba", "te", "saint", ["Tarigonda Vengamamba"], ["Tarigonda Vengamamba", "Tirumala Vengamamba annaprasadam"], "the poet-devotee whose name is on Tirumala's free food hall")

# ── Devotees and temples (2026-10-21) ────────────────────────────────────────
# The two breakout Shorts were a devotee story (Kannappa, Telugu, 1,370) and a temple
# with one striking custom (Karni Mata, Hindi, 1,266); the epic myths and "mystery"
# places flopped (Samudra Manthan 9, Ravana lifting Kailash 50, Bhangarh 39). Every
# angle below was checked against its Wikipedia text before adding. Legends and beliefs
# (Yaganti's Nandi, Banke Bihari's curtain) are told as what devotees believe, never as fact.
# Left out on purpose: Arasavalli (its article leads into a temple destruction) and
# Mantralayam/Dwaraka Tirumala/Sri Kurmam/Vemulawada (articles too thin to carry a story).
# Barbarika, Sudama and Shabari would fit here but are already pan-Indian entries above.
add2("sammakka_saralamma", "te", "folk", ["Sammakka Saralamma Jatara"], ["Medaram jatara", "Sammakka Saralamma"], "devotees offer jaggery equal to their own body weight to two tribal goddesses")
add2("ahobilam", "te", "myth", ["Ahobilam"], ["Ahobilam temple", "Ahobilam Narasimha"], "nine shrines of Narasimha on one hill, where he is said to have appeared from the pillar")
add2("siddhendra_yogi", "te", "saint", ["Kuchipudi"], ["Kuchipudi dance", "Kuchipudi village"], "an orphan named Siddhendra Yogi who shaped Kuchipudi, Andhra's classical dance")
add2("annavaram", "te", "myth", ["Satyanarayana Temple, Annavaram"], ["Annavaram temple", "Annavaram Satyanarayana"], "the god who told a devotee in a dream that he would appear on Ratnagiri hill")
add2("yaganti", "te", "wonder", ["Yaganti temple"], ["Yaganti temple", "Yaganti Nandi"], "a stone Nandi that devotees believe keeps growing, and the legend of why no crows come")
add2("pancharama", "te", "myth", ["Pancharama Kshetras"], ["Draksharamam temple", "Pancharama temple"], "Tarakasura's linga broke into five pieces, and each became a temple in Andhra")
add2("vontimitta", "te", "wonder", ["Kodandarama Temple, Vontimitta"], ["Vontimitta temple", "Kodandarama temple Vontimitta"], "a Rama temple where Hanuman is missing from the sanctum")
add2("mahanandi", "te", "engineering", ["Mahanandi"], ["Mahanandi temple", "Mahanandi pushkarini"], "a temple tank whose water is always kept exactly five feet deep")
add2("thousand_pillar", "te", "engineering", ["Thousand Pillar Temple"], ["Thousand Pillar Temple Hanamkonda", "Thousand pillar temple Nandi"], "Kakatiya builders laid its foundation on a bed of sand")
add2("kotappakonda", "te", "folk", ["Kotappakonda"], ["Kotappakonda temple", "Kotappakonda prabha"], "villages build giant Prabha towers for Shivaratri and over a million devotees come")
add2("surdas", "hi", "saint", ["Surdas"], ["Surdas painting", "Surdas"], "the blind poet whose songs describe the child Krishna")
add2("banke_bihari", "hi", "wonder", ["Banke Bihari Temple"], ["Banke Bihari temple Vrindavan", "Banke Bihari Vrindavan"], "the curtain is drawn in front of the deity every five minutes, and why devotees believe it must be")
add2("kedarnath", "hi", "wonder", ["Kedarnath Temple"], ["Kedarnath temple", "Kedarnath"], "a stone temple high in the Himalayas that stood through the 2013 floods")
add2("mahakaleshwar", "hi", "wonder", ["Mahakaleshwar Jyotirlinga"], ["Mahakaleshwar temple Ujjain", "Mahakaleshwar"], "the Jyotirlinga whose deity faces south")
add2("omkareshwar", "hi", "wonder", ["Omkareshwar Temple"], ["Omkareshwar temple", "Omkareshwar island"], "a Jyotirlinga on a Narmada island said to be shaped like the symbol Om")
add2("vaishno_devi", "hi", "wonder", ["Vaishno Devi Temple"], ["Vaishno Devi temple", "Vaishno Devi Trikuta"], "the cave shrine on Trikuta mountain that pilgrims climb to")
add2("tungnath", "hi", "wonder", ["Tungnath"], ["Tungnath temple", "Tungnath"], "the highest of the five Panch Kedar temples, among the highest Shiva temples in the world")
add2("badrinath", "hi", "wonder", ["Badrinath Temple"], ["Badrinath temple", "Badrinath Tapt Kund"], "hot sulphur springs bubbling just below a temple in the snowbound Himalayas")
add2("neelkanth", "hi", "myth", ["Neelkanth Mahadev Temple"], ["Neelkanth Mahadev temple", "Neelkanth Mahadev Rishikesh"], "the spot where Shiva is said to have drunk the poison from the churning of the ocean")

# ── English: Strange But True (the renamed Money Sorted channel, 2026-10-23) ──────
# Same shape as Ajab Gajab's record (Mysore Palace, 14.3k): a famous place plus one dramatic true event.
add2("pisa_tower", "en", "engineering", ["Leaning Tower of Pisa"], ["Leaning Tower of Pisa", "Pisa tower"], "it started leaning before it was even finished, and builders kept going for 200 years")
add2("big_ben_pennies", "en", "engineering", ["Big Ben"], ["Elizabeth Tower Big Ben", "Big Ben clock face"], "the great clock is kept on time by adding or removing old pennies")
add2("eiffel_temporary", "en", "engineering", ["Eiffel Tower"], ["Eiffel Tower construction", "Eiffel Tower 1889"], "the tower was only meant to stand for 20 years")
add2("eiffel_sold", "en", "history", ["Victor Lustig"], ["Eiffel Tower 1920s", "Victor Lustig"], "the con man who sold the Eiffel Tower for scrap")
add2("london_bridge_arizona", "en", "history", ["London Bridge (Lake Havasu City)"], ["London Bridge Lake Havasu", "London Bridge Arizona"], "London Bridge was sold, shipped and rebuilt in the Arizona desert")
add2("tower_bridge_bus", "en", "history", ["Tower Bridge"], ["Tower Bridge raised", "Tower Bridge London"], "a double-decker bus jumped the gap as the bridge began to open")
add2("alcatraz_escape", "en", "history", ["June 1962 Alcatraz escape attempt"], ["Alcatraz Island", "Alcatraz cell"], "three men left fake heads in their beds and vanished from Alcatraz")
add2("molasses_flood", "en", "history", ["Great Molasses Flood"], ["Great Molasses Flood", "Boston North End 1919"], "a wave of molasses rolled through the streets of Boston")
add2("empire_state_crash", "en", "history", ["1945 Empire State Building B-25 crash"], ["Empire State Building 1945 crash", "Empire State Building"], "a bomber flew into the Empire State Building in fog, and a lift operator survived a 75-storey fall")
add2("mona_lisa_theft", "en", "history", ["Mona Lisa"], ["Mona Lisa Louvre empty wall 1911", "Mona Lisa"], "the day the Mona Lisa vanished from the Louvre and nobody noticed for a day")
add2("winchester_house", "en", "wonder", ["Winchester Mystery House"], ["Winchester Mystery House", "Winchester House stairs"], "a mansion with stairs that lead into the ceiling, built non-stop for 38 years")
add2("statue_liberty", "en", "engineering", ["Statue of Liberty"], ["Statue of Liberty construction", "Statue of Liberty"], "the statue was once shiny copper-brown, and it turned green on its own")
add2("golden_gate_color", "en", "engineering", ["Golden Gate Bridge"], ["Golden Gate Bridge", "Golden Gate Bridge construction"], "its famous orange was only meant to be the primer")
add2("rushmore_room", "en", "wonder", ["Mount Rushmore"], ["Mount Rushmore", "Mount Rushmore construction"], "a hidden chamber behind the faces that was never finished")
add2("tower_ravens", "en", "folk", ["Ravens of the Tower of London"], ["Tower of London ravens", "Tower of London"], "the legend that the kingdom falls if the ravens ever leave")
add2("petra", "en", "wonder", ["Petra"], ["Petra Treasury", "Petra Jordan"], "a city carved into a cliff that the Western world forgot for centuries")
add2("stonehenge", "en", "wonder", ["Stonehenge"], ["Stonehenge", "Stonehenge bluestones"], "some of its stones were dragged about 150 miles from Wales")
add2("colosseum_flood", "en", "history", ["Colosseum"], ["Colosseum Rome", "Colosseum interior hypogeum"], "the arena was flooded to stage sea battles")
add2("neuschwanstein", "en", "history", ["Neuschwanstein Castle", "Ludwig II of Bavaria"], ["Neuschwanstein Castle", "Ludwig II of Bavaria"], "the fairy-tale castle whose king died mysteriously before it was finished")
add2("sydney_opera", "en", "engineering", ["Sydney Opera House", "Jørn Utzon"], ["Sydney Opera House", "Sydney Opera House construction"], "its architect quit and never saw the building finished")
add2("chichen_itza", "en", "wonder", ["Chichen Itza", "El Castillo, Chichen Itza"], ["El Castillo Chichen Itza", "Chichen Itza equinox serpent"], "on the equinox a shadow serpent slides down the pyramid")
add2("hoover_dam", "en", "engineering", ["Hoover Dam"], ["Hoover Dam", "Hoover Dam construction"], "the concrete would have taken over a century to cool on its own")
add2("darvaza", "en", "wonder", ["Darvaza gas crater"], ["Darvaza gas crater", "Door to Hell Turkmenistan"], "a crater set on fire on purpose that kept burning for decades")
add2("pompeii", "en", "history", ["Pompeii", "Eruption of Mount Vesuvius in 79 AD"], ["Pompeii ruins Vesuvius", "Pompeii"], "a whole Roman city buried in a day and found again 1,500 years later")
add2("machu_picchu", "en", "wonder", ["Machu Picchu"], ["Machu Picchu", "Machu Picchu terraces"], "the Inca city the Spanish conquerors never found")

# Wait, That's Real? 2026-10-31 (owner): 2 Shorts a day needs more stock. First block: place + human-twist
# stories in the shape of the channel's best (Petra goat, Eiffel lunch, Hoover Dam). Second block: Quizora's
# narrative story_bank.json candidates (screened 10-09 for a free lead image), moving with the true-story
# lane to WTR; anything Quizora already published is left out.
add2("tunguska", "en", "wonder", ["Tunguska event"], ["Tunguska event trees", "Tunguska 1908"], "something flattened 80 million trees in Siberia and left no crater")
add2("kowloon_city", "en", "history", ["Kowloon Walled City"], ["Kowloon Walled City", "Kowloon Walled City aerial"], "33,000 people lived in one city block with no laws and no sunlight")
add2("seed_vault", "en", "engineering", ["Svalbard Global Seed Vault"], ["Svalbard Global Seed Vault", "Svalbard"], "a doomsday vault in the Arctic holds a backup of the world's crops")
add2("centralia", "en", "wonder", ["Centralia, Pennsylvania", "Centralia mine fire"], ["Centralia Pennsylvania", "Centralia mine fire"], "a town has had a fire burning under it since 1962")
add2("paris_catacombs", "en", "history", ["Catacombs of Paris"], ["Catacombs of Paris", "Paris catacombs ossuary"], "six million people are buried in tunnels under Paris")
add2("hashima", "en", "history", ["Hashima Island"], ["Hashima Island", "Gunkanjima"], "the most crowded place on Earth was emptied in a single year")
add2("mary_celeste", "en", "history", ["Mary Celeste"], ["Mary Celeste", "Mary Celeste ship"], "a ship found sailing with no one on board and the food still there")
add2("halifax_explosion", "en", "history", ["Halifax Explosion"], ["Halifax Explosion", "Halifax 1917"], "two ships collided and made the biggest blast before the atomic bomb")
add2("roy_sullivan", "en", "history", ["Roy Sullivan"], ["Roy Sullivan", "Shenandoah National Park"], "a park ranger was hit by lightning seven times and survived them all")
add2("greyfriars_bobby", "en", "folk", ["Greyfriars Bobby"], ["Greyfriars Bobby", "Greyfriars Kirkyard"], "a little dog guarded his owner's grave in Edinburgh for 14 years")
add2("great_wall_rice", "en", "engineering", ["Great Wall of China"], ["Great Wall of China", "Great Wall Mutianyu"], "parts of the Great Wall are held together with sticky rice")
add2("terracotta_well", "en", "history", ["Terracotta Army"], ["Terracotta Army", "Terracotta Army pit"], "farmers digging a well found an underground army of 8,000 soldiers")
add2("lascaux_dog", "en", "history", ["Lascaux"], ["Lascaux cave painting", "Lascaux"], "teenagers chasing their dog fell into a cave full of 17,000-year-old paintings")
add2("dead_sea_scrolls", "en", "history", ["Dead Sea Scrolls", "Qumran Caves"], ["Qumran Caves", "Dead Sea Scrolls"], "a shepherd threw a stone into a cave and found 2,000-year-old scrolls")
add2("rosetta_stone", "en", "history", ["Rosetta Stone"], ["Rosetta Stone", "Rosetta Stone British Museum"], "soldiers rebuilding a fort found the stone that unlocked hieroglyphs")
add2("antikythera", "en", "engineering", ["Antikythera mechanism"], ["Antikythera mechanism", "Antikythera mechanism fragment"], "divers found a 2,000-year-old computer in a shipwreck")
add2("sagrada_familia", "en", "engineering", ["Sagrada Família"], ["Sagrada Familia", "Sagrada Familia construction"], "a church in Barcelona has been under construction for over 140 years")
add2("elmer_mccurdy", "en", "history", ["Elmer McCurdy"], ["Elmer McCurdy", "The Pike Long Beach"], "a TV crew found a real outlaw's body hanging in a funhouse")
add2("kola_borehole", "en", "engineering", ["Kola Superdeep Borehole"], ["Kola Superdeep Borehole", "Kola Superdeep Borehole cap"], "the deepest hole ever dug is now a rusty cap the size of a dinner plate")
add2("coral_castle", "en", "wonder", ["Coral Castle"], ["Coral Castle", "Coral Castle Florida"], "one small man moved tons of coral rock alone, at night, and never said how")
add2("flannan_isles", "en", "history", ["Flannan Isles Lighthouse"], ["Flannan Isles Lighthouse", "Flannan Isles"], "three lighthouse keepers vanished from a tiny island in 1900")
add2("sedlec_ossuary", "en", "wonder", ["Sedlec Ossuary"], ["Sedlec Ossuary", "Sedlec Ossuary chandelier"], "a chapel decorated with the bones of 40,000 people")
add2("great_stink", "en", "history", ["Great Stink"], ["Great Stink 1858", "Joseph Bazalgette"], "London smelled so bad that Parliament finally built the sewers")
add2("crown_jewels_blood", "en", "history", ["Thomas Blood"], ["Thomas Blood", "Crown Jewels Tower of London"], "a man stole the Crown Jewels, got caught, and the king pardoned him")
add2("roanoke", "en", "history", ["Roanoke Colony"], ["Roanoke Colony", "Croatoan"], "a whole colony vanished and left one word carved on a post")
add2("gimli_glider", "en", "engineering", ["Gimli Glider"], ["Gimli Glider", "Air Canada Flight 143"], "a jet ran out of fuel at 41,000 feet and glided to a racetrack")
add2("christmas_truce", "en", "history", ["Christmas truce"], ["Christmas truce 1914", "Christmas truce"], "enemy soldiers in World War I stopped fighting to play football")
# from quizora/narrative/story_bank.json
add2("phineas_gage", "en", "history", ["Phineas Gage"], ["Phineas Gage", "Phineas Gage tamping iron"], "an iron rod went straight through his skull, and he walked to the doctor")
add2("mike_chicken", "en", "folk", ["Mike the Headless Chicken"], ["Mike the Headless Chicken", "Fruita Colorado"], "a chicken lived for 18 months without a head and went on tour")
add2("cadaver_synod", "en", "history", ["Cadaver Synod"], ["Cadaver Synod", "Pope Formosus"], "a pope dug up the pope before him and put the corpse on trial")
add2("ching_shih", "en", "history", ["Zheng Yi Sao"], ["Zheng Yi Sao", "Chinese junk ship"], "a pirate queen commanded 1,800 ships and retired rich")
add2("laughter_epidemic", "en", "history", ["Tanganyika laughter epidemic"], ["Kashasha Tanzania", "Lake Victoria Tanzania"], "a laughing fit spread so far it shut schools for months")
add2("anna_anderson", "en", "history", ["Anna Anderson"], ["Anna Anderson", "Grand Duchess Anastasia Nikolaevna"], "she claimed to be the lost Grand Duchess Anastasia for 60 years")
add2("year_without_summer", "en", "wonder", ["Year Without a Summer", "1815 eruption of Mount Tambora"], ["Mount Tambora", "Year Without a Summer"], "one volcano cancelled summer across the world in 1816")
add2("radium_girls", "en", "history", ["Radium Girls"], ["Radium Girls", "radium dial painters"], "factory girls were told to lick the glowing paint off their brushes")
add2("kaspar_hauser", "en", "history", ["Kaspar Hauser"], ["Kaspar Hauser", "Nuremberg old town"], "a teenager walked into Nuremberg who seemed to have lived his whole life in a cell")
add2("alexander_selkirk", "en", "history", ["Alexander Selkirk"], ["Robinson Crusoe Island", "Alexander Selkirk"], "the real Robinson Crusoe chose to be left on an island, and stayed four years")
add2("cottingley_fairies", "en", "history", ["Cottingley Fairies"], ["Cottingley Fairies", "Cottingley Beck"], "two girls fooled Sherlock Holmes's creator with paper fairies")
add2("clever_hans", "en", "folk", ["Clever Hans"], ["Clever Hans", "Clever Hans horse"], "a horse that could do maths, until someone asked the right question")
add2("timothy_dexter", "en", "history", ["Timothy Dexter"], ["Timothy Dexter", "Newburyport Massachusetts"], "every terrible idea he had made him richer")
add2("psalmanazar", "en", "history", ["George Psalmanazar"], ["George Psalmanazar", "Formosa map 18th century"], "a Frenchman convinced London he came from Formosa and invented its language")
add2("princess_caraboo", "en", "history", ["Princess Caraboo"], ["Princess Caraboo", "Almondsbury"], "a shoemaker's daughter posed as a princess from an island that didn't exist")
add2("nain_singh", "en", "history", ["Nain Singh"], ["Nain Singh Rawat", "Lhasa Potala"], "he mapped Tibet in secret by counting his own steps on prayer beads")
add2("ned_kelly", "en", "history", ["Ned Kelly"], ["Ned Kelly armour", "Glenrowan"], "an outlaw made armour from ploughs and walked into a gunfight")
add2("golden_stool", "en", "history", ["War of the Golden Stool"], ["Golden Stool Ashanti", "Kumasi"], "an empire went to war rather than let a governor sit on a stool")
add2("pelorus_jack", "en", "folk", ["Pelorus Jack"], ["Pelorus Jack", "French Pass New Zealand"], "a dolphin guided ships for 24 years and got its own law")
add2("lykov_family", "en", "history", ["Lykov family"], ["Lykov family", "Abakan River"], "geologists found a family that had lived 40 years in the Siberian wild without news of the world")
add2("karansebes", "en", "history", ["Battle of Karánsebes"], ["Karansebes", "Timis River"], "an army may have fought itself in the dark and lost")
add2("defenestrations", "en", "history", ["Defenestrations of Prague"], ["Defenestrations of Prague", "Prague Castle"], "Prague kept starting wars by throwing people out of windows")
add2("hemingway_crashes", "en", "history", ["Ernest Hemingway"], ["Ernest Hemingway 1950s", "Murchison Falls"], "two plane crashes in two days, then he read his own obituaries")

# ── Daily feed (feed.py, 2026-11-01) ─────────────────────────────────────────
# Wikipedia-grounded strange-but-true candidates for WTR, scored by Gemini and filtered (no living people,
# enough source text and Commons images). Merged as ordinary "en" entries; a hand-written key always wins.
import json as _json, pathlib as _pl
for _f in _json.loads((_pl.Path(__file__).with_name("bank_feed.json")).read_text(encoding="utf-8")) \
        if _pl.Path(__file__).with_name("bank_feed.json").exists() else []:
    if _f["key"] not in {_s["key"] for _s in S}:
        add2(_f["key"], "en", _f["kind"], _f["wiki"], _f["art"], _f["angle"])
