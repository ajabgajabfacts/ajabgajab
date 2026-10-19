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
add("kashi_vishwanath", "hi", "wonder", ["Kashi Vishwanath Temple"], ["Kashi Vishwanath Temple", "Varanasi ghats painting"])
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
