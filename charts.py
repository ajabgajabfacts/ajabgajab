# -*- coding: utf-8 -*-
"""BrainBolt content engine — quiz/game Shorts, 100% original renders.

Named charts.py so the (shared) pipeline's imports need no changes.
Key property: narration is built DETERMINISTICALLY from the question data —
no LLM at runtime, so answers can never hallucinate and nothing rate-limits.
The spoken "three... two... one..." countdown IS the think window, keeping
audio and visuals in sync via word-count proportional timing (same trick as
the caption layer).

Add quizzes freely: append to QUIZZES — no new code unless a new format.
Every answer must be objectively verifiable; put the receipt in 'fact'.
"""
import re
import textwrap
from functools import partial
from pathlib import Path

from PIL import Image

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import animation

W_PX, H_PX, DPI = 1020, 1400, 96
BG = "#0C0E1C"

# The finished Short is 1080x1920 and build_video scales this chart to the full
# width, then drops it at 13% down the frame. CHART_BAND is the strip of the
# final frame the chart therefore covers — the photo background is sliced along
# it so the chart's copy and the frame's copy line up exactly.
VIDEO_W, VIDEO_H = 1080, 1920
_CHART_TOP       = int(VIDEO_H * 0.13)
CHART_BAND       = (_CHART_TOP, _CHART_TOP + int(H_PX * VIDEO_W / W_PX))


def _hex(a):
    return "#{:02X}{:02X}{:02X}".format(*a)


# ── Question bank ─────────────────────────────────────────────────────────────
# format: trivia (3 options + reveal) | riddle (open + reveal) | wyr (poll, no answer)
QUIZZES = [
    dict(key="space_basics", format="trivia", concept="space", title="Only 1% Get All 3 Space Questions Right",
         hook="Only 1 percent get all three of these space questions right.",
         questions=[
             dict(q="Which planet has the most moons?", options=["Jupiter", "Saturn", "Neptune"],
                  answer=1, fact="Saturn — 274 confirmed moons, far ahead of Jupiter."),
             dict(q="Which planet is the hottest?", options=["Mercury", "Venus", "Mars"],
                  answer=1, fact="Venus — 465 degrees Celsius, hotter than Mercury despite being further from the Sun."),
             dict(q="How long does sunlight take to reach Earth?", options=["8 seconds", "8 minutes", "8 hours"],
                  answer=1, fact="About 8 minutes and 20 seconds."),
         ]),
    dict(key="trick_questions_1", format="trivia", concept="trick", title="3 Trick Questions That Fool 99% of People",
         hook="These three trick questions fool 99 percent of people.",
         questions=[
             dict(q="Which is heavier: a ton of bricks or a ton of feathers?", options=["Bricks", "Feathers", "They're equal"],
                  answer=2, fact="A ton is a ton — exactly the same weight."),
             dict(q="How many months have 28 days?", options=["1", "6", "All 12"],
                  answer=2, fact="Every month has at least 28 days."),
             dict(q="Is the Great Wall of China visible from space with the naked eye?", options=["Yes", "No", "Only at night"],
                  answer=1, fact="No — astronauts confirm it's too narrow to see unaided."),
         ]),
    dict(key="animal_iq", format="trivia", concept="animals", title="The Octopus Question Everyone Gets Wrong",
         hook="Question two fools almost everyone. Will you be one of them?",
         questions=[
             dict(q="What is the fastest land animal?", options=["Greyhound", "Cheetah", "Pronghorn"],
                  answer=1, fact="The cheetah — up to 112 kilometers per hour."),
             dict(q="How many hearts does an octopus have?", options=["1", "3", "9"],
                  answer=1, fact="Three hearts — and nine brains."),
             dict(q="What is the only mammal that can truly fly?", options=["Flying squirrel", "Sugar glider", "Bat"],
                  answer=2, fact="The bat — the others only glide."),
         ]),
    dict(key="body_numbers", format="trivia", concept="body", title="How Well Do You Know Your Own Body?",
         hook="Most people fail question three about their own body.",
         questions=[
             dict(q="How many bones does an adult human have?", options=["106", "206", "306"],
                  answer=1, fact="206 — babies start with about 300 that fuse over time."),
             dict(q="What is the hardest substance in your body?", options=["Skull bone", "Tooth enamel", "Kneecap"],
                  answer=1, fact="Tooth enamel — harder than steel by scratch resistance."),
             dict(q="Roughly how many times does your heart beat per day?", options=["10,000", "100,000", "1 million"],
                  answer=1, fact="About 100,000 beats every single day."),
         ]),
    dict(key="geo_caps", format="trivia", concept="geography", title="99% Fail the Australia Question",
         hook="99 percent of non-Australians fail question one.",
         questions=[
             dict(q="What is the capital of Australia?", options=["Sydney", "Melbourne", "Canberra"],
                  answer=2, fact="Canberra — purpose-built because Sydney and Melbourne couldn't agree."),
             dict(q="Which country has the most time zones?", options=["Russia", "USA", "France"],
                  answer=2, fact="France — 12 to 13 zones thanks to overseas territories."),
             dict(q="Which continent has the most countries?", options=["Asia", "Africa", "Europe"],
                  answer=1, fact="Africa — 54 countries."),
         ]),
    dict(key="history_firsts", format="trivia", concept="history", title="The Oxford Question Breaks Brains",
         hook="Question three breaks almost everyone. You will not see it coming.",
         questions=[
             dict(q="In which year did humans first walk on the Moon?", options=["1961", "1969", "1975"],
                  answer=1, fact="1969 — Apollo 11, July 20."),
             dict(q="What was the first animal to orbit Earth?", options=["A monkey", "A dog", "A mouse"],
                  answer=1, fact="Laika the dog, aboard Sputnik 2 in 1957."),
             dict(q="Which came first: Oxford University or the Aztec Empire?", options=["Oxford", "Aztec Empire", "Same century"],
                  answer=0, fact="Oxford — teaching by 1096; the Aztec Empire formed in 1428."),
         ]),
    dict(key="price_launch", format="trivia", concept="price", title="Guess the Price: 1907 to 2007",
         hook="Guess three prices from history. Most people miss all three.",
         questions=[
             dict(q="Launch price of the first iPhone in 2007?", options=["$299", "$499", "$999"],
                  answer=1, fact="$499 — and critics called it absurdly expensive."),
             dict(q="Price of a Ford Model T in 1925?", options=["$260", "$1,200", "$4,000"],
                  answer=0, fact="About $260 — mass production crushed the price."),
             dict(q="A New York subway ride in 1950?", options=["10 cents", "50 cents", "$1"],
                  answer=0, fact="10 cents — it held that price for years."),
         ]),
    dict(key="penny_doubling", format="trivia", concept="money", title="$1M Now or a Penny Doubled for 30 Days?",
         hook="Your gut will get question one wrong. Almost everyone's does.",
         questions=[
             dict(q="Which is worth more: $1 million today, or 1 cent doubled every day for 30 days?", options=["The $1 million", "The doubling penny", "About equal"],
                  answer=1, fact="The penny — it becomes $5.37 million. Doubling is violent."),
             dict(q="At $1,000 a day, how long does $1 billion last?", options=["27 years", "274 years", "2,740 years"],
                  answer=2, fact="2,740 years. A million lasts under 3."),
             dict(q="What fraction of its buying power has $100 from 1970 kept?", options=["About half", "About a quarter", "About an eighth"],
                  answer=2, fact="About 12 percent — inflation ate the rest."),
         ]),
    dict(key="riddles_classic", format="riddle", concept="riddles", title="3 Riddles — Solve Even One and You're Sharp",
         hook="Solve even one of these and you're sharper than most.",
         questions=[
             dict(q="What gets wetter the more it dries?", options=[], answer=-1, fact="A towel."),
             dict(q="What has hands but cannot clap?", options=[], answer=-1, fact="A clock."),
             dict(q="The more you take, the more you leave behind. What am I?", options=[], answer=-1, fact="Footsteps."),
         ]),
    dict(key="riddles_2", format="riddle", concept="riddles", title="The Riddle 97% Answer Too Fast",
         hook="Most people answer number two too fast — and wrong.",
         questions=[
             dict(q="What goes up but never comes down?", options=[], answer=-1, fact="Your age."),
             dict(q="I speak without a mouth and hear without ears. What am I?", options=[], answer=-1, fact="An echo."),
             dict(q="What can you break without touching it?", options=[], answer=-1, fact="A promise."),
         ]),
    dict(key="wyr_money", format="wyr", concept="wyr", title="Would You Rather: The Money Edition",
         hook="Two choices. No wrong answer. But your pick says everything.",
         questions=[
             dict(q="$10,000 every month forever — or $5 million right now?", options=["$10k/month forever", "$5M right now"],
                  answer=-1, fact=""),
             dict(q="Never pay for flights again — or never pay for food again?", options=["Free flights", "Free food"],
                  answer=-1, fact=""),
             dict(q="Know every fact — or never need sleep?", options=["Know everything", "Never sleep"],
                  answer=-1, fact=""),
         ]),
    dict(key="space_deep", format="trivia", concept="space", title="Venus Will Ruin Your Day (Quiz)",
         hook="Only one percent get all three of these space questions right.",
         questions=[
             dict(q="On Venus, which is longer: a day or a year?", options=["The day", "The year", "They're equal"],
                  answer=0, fact="The day — 243 Earth days versus a 225-day year."),
             dict(q="How many Earths fit inside the Sun?", options=["13,000", "130,000", "1.3 million"],
                  answer=2, fact="About 1.3 million."),
             dict(q="What is the closest star to Earth?", options=["Alpha Centauri", "The Sun", "Sirius"],
                  answer=1, fact="The Sun — the trick 30 percent still miss."),
         ]),
    dict(key="food_facts", format="trivia", concept="food", title="The Most Stolen Food on Earth Is...",
         hook="Question two is the most stolen food on Earth. Can you guess it?",
         questions=[
             dict(q="Which food never spoils?", options=["Rice", "Honey", "Salt beef"],
                  answer=1, fact="Honey — edible pots were found in Egyptian tombs."),
             dict(q="What is the most stolen food in the world?", options=["Chocolate", "Cheese", "Coffee"],
                  answer=1, fact="Cheese — about 4 percent of it is stolen globally."),
             dict(q="What did the Aztecs use cocoa beans as?", options=["Medicine only", "Money", "Paint"],
                  answer=1, fact="Currency — you could literally spend chocolate."),
         ]),
    dict(key="flags_countries", format="trivia", concept="geography", title="Only Flag Nerds Get 3/3",
         hook="Only flag nerds get all three.",
         questions=[
             dict(q="Which country's flag is not rectangular?", options=["Switzerland", "Nepal", "Qatar"],
                  answer=1, fact="Nepal — two stacked triangles, the only one on Earth."),
             dict(q="What is the smallest country in the world?", options=["Monaco", "Vatican City", "San Marino"],
                  answer=1, fact="Vatican City — 0.44 square kilometers."),
             dict(q="Which country is bigger than Pluto?", options=["Canada", "Russia", "China"],
                  answer=1, fact="Russia — 17.1 million square km versus Pluto's 16.65."),
         ]),
    dict(key="tech_history", format="trivia", concept="tech", title="Nintendo Is HOW Old? (Quiz)",
         hook="Question one is older than your great-grandparents.",
         questions=[
             dict(q="In which year was Nintendo founded?", options=["1889", "1949", "1979"],
                  answer=0, fact="1889 — as a playing-card company, same year the Eiffel Tower opened."),
             dict(q="How much memory did the Apollo 11 computer have?", options=["74 KB", "74 MB", "74 GB"],
                  answer=0, fact="74 kilobytes — your phone has millions of times more."),
             dict(q="What did the first computer ENIAC weigh?", options=["270 kg", "2.7 tonnes", "27 tonnes"],
                  answer=2, fact="27 tonnes — about four elephants."),
         ]),
    dict(key="wyr_powers", format="wyr", concept="wyr", title="Would You Rather: Impossible Powers",
         hook="Impossible powers. You can only pick one.",
         questions=[
             dict(q="Fly at walking speed — or teleport once per day?", options=["Slow flight", "Daily teleport"],
                  answer=-1, fact=""),
             dict(q="Rewind 10 seconds anytime — or pause time for 10 seconds once a day?", options=["Rewind", "Pause"],
                  answer=-1, fact=""),
             dict(q="Talk to animals — or speak every human language?", options=["Animals", "All languages"],
                  answer=-1, fact=""),
         ]),
    dict(key="odds_quiz", format="trivia", concept="odds", title="You're Guessing These Odds Wrong",
         hook="You will guess at least one of these odds wrong.",
         questions=[
             dict(q="What's deadlier per year worldwide?", options=["Sharks", "Vending machines", "Mosquitoes"],
                  answer=2, fact="Mosquitoes — about 700,000 deaths a year via disease."),
             dict(q="Lifetime odds of being struck by lightning?", options=["1 in 15,000", "1 in 1.5 million", "1 in 150 million"],
                  answer=0, fact="About 1 in 15,000 — vastly better than lottery odds."),
             dict(q="Odds of a royal flush in a 5-card deal?", options=["1 in 6,497", "1 in 649,740", "1 in 64 million"],
                  answer=1, fact="1 in 649,740 — deal a hand a day and you'd wait 1,780 years."),
         ]),
    dict(key="earth_extremes", format="trivia", concept="geography", title="Earth Extremes: 3 Questions, 0 Mercy",
         hook="Three questions about Earth. Almost nobody gets all three.",
         questions=[
             dict(q="What's deeper: the Mariana Trench, or Everest is tall?", options=["Everest is taller", "The trench is deeper", "Equal"],
                  answer=1, fact="The trench — 10,935 meters. Everest would sink completely."),
             dict(q="Which is bigger: the Pacific Ocean or all land combined?", options=["All land", "The Pacific", "Equal"],
                  answer=1, fact="The Pacific — 165 million square km versus 149 for all land."),
             dict(q="What percentage of the seafloor is mapped in high resolution?", options=["About 26%", "About 56%", "About 86%"],
                  answer=0, fact="About 26 percent — we've mapped Mars better."),
         ]),
    # ── BANK EXPANSION ──────────────────────────────────────────────────────
    dict(key="weird_history", format="trivia", concept="history", title="The Shortest War Lasted HOW Long?",
         hook="Three pieces of history that sound fake. You will doubt all three.",
         questions=[
             dict(q="How long did the shortest war in history last?", options=["38 minutes", "38 hours", "38 days"],
                  answer=0, fact="About 38 minutes — Britain versus Zanzibar, 1896."),
             dict(q="What did Einstein win his Nobel Prize for?", options=["Relativity", "The photoelectric effect", "E=mc squared"],
                  answer=1, fact="The photoelectric effect — not relativity."),
             dict(q="The world's oldest company was founded in which century?", options=["6th century", "12th century", "18th century"],
                  answer=0, fact="Kongo Gumi, Japan — building temples since 578 AD."),
         ]),
    dict(key="accidental_inventions", format="trivia", concept="tech", title="These 3 Things Were Invented by Accident",
         hook="All three of these were invented by accident. Bet you miss two.",
         questions=[
             dict(q="The microwave oven was discovered when radar melted a...", options=["Candle", "Chocolate bar", "Sandwich"],
                  answer=1, fact="A chocolate bar in engineer Percy Spencer's pocket, 1945."),
             dict(q="Bubble wrap was originally invented as...", options=["Wallpaper", "Packaging", "Insulation"],
                  answer=0, fact="Textured wallpaper — it flopped, then shipping saved it."),
             dict(q="Velcro was inspired by...", options=["Octopus suckers", "Burrs on a dog", "Gecko feet"],
                  answer=1, fact="Burrs stuck to George de Mestral's dog after a walk in 1941."),
         ]),
    dict(key="body_extremes", format="trivia", concept="body", title="Your Blood Vessels Reach HOW Far?",
         hook="Question two about your own blood vessels sounds fake.",
         questions=[
             dict(q="Are you taller in the morning or the evening?", options=["Morning", "Evening", "Same height"],
                  answer=0, fact="Morning — your spine compresses about 1 cm during the day."),
             dict(q="Laid end to end, your blood vessels would stretch about...", options=["100 km", "10,000 km", "100,000 km"],
                  answer=2, fact="Roughly 100,000 km — two and a half times around Earth."),
             dict(q="Roughly what share of your DNA do you share with a banana?", options=["About 1%", "About 60%", "About 95%"],
                  answer=1, fact="Around 60% of banana genes have a human counterpart."),
         ]),
    dict(key="animal_extremes", format="trivia", concept="animals", title="The Animal That Never Drinks Water",
         hook="One of these animals never drinks water. Only one in ten know which.",
         questions=[
             dict(q="Which animal can go its whole life without drinking water?", options=["Camel", "Kangaroo rat", "Fennec fox"],
                  answer=1, fact="The kangaroo rat — it extracts all its water from seeds."),
             dict(q="Which animal has the strongest measured bite?", options=["Great white shark", "Saltwater crocodile", "Hippo"],
                  answer=1, fact="The saltwater crocodile — about 3,700 psi."),
             dict(q="What is the slowest mammal on Earth?", options=["Koala", "Three-toed sloth", "Manatee"],
                  answer=1, fact="The three-toed sloth — top speed around 0.24 kilometers per hour."),
         ]),
    dict(key="space_leftovers", format="trivia", concept="space", title="Footprints on the Moon Last HOW Long?",
         hook="Only one in ten get all three of these Moon questions right.",
         questions=[
             dict(q="How many times does the ISS orbit Earth per day?", options=["4", "16", "48"],
                  answer=1, fact="16 orbits — a sunrise every 90 minutes."),
             dict(q="How long is a year on Mercury?", options=["88 days", "365 days", "687 days"],
                  answer=0, fact="88 Earth days — it sprints around the Sun."),
             dict(q="How long will the Apollo footprints last on the Moon?", options=["Decades", "Centuries", "Millions of years"],
                  answer=2, fact="Millions of years — no wind, no rain, nothing to erase them."),
         ]),
    dict(key="sports_numbers", format="trivia", concept="trick", title="Olympic Gold Is Mostly... Not Gold",
         hook="Question one ruins Olympic gold for everyone. Think you know it?",
         questions=[
             dict(q="An Olympic gold medal is mostly made of...", options=["Gold", "Silver", "Bronze"],
                  answer=1, fact="About 92.5 percent silver — only around 6 grams of actual gold."),
             dict(q="What's the fastest recorded projectile in ball sports?", options=["Golf drive", "Badminton smash", "Jai alai ball"],
                  answer=1, fact="A badminton smash — clocked over 490 kilometers per hour."),
             dict(q="Who invented basketball?", options=["A PE teacher", "A soldier", "A factory owner"],
                  answer=0, fact="James Naismith, a Canadian PE teacher, in 1891 — with peach baskets."),
         ]),
    dict(key="language_letters", format="trivia", concept="trick", title="The Most Common Letter Isn't What You Think",
         hook="Only word nerds sweep this round.",
         questions=[
             dict(q="What is the most common letter in English?", options=["A", "E", "T"],
                  answer=1, fact="E — about 11 percent of all letters written."),
             dict(q="Which language has the most native speakers?", options=["English", "Mandarin Chinese", "Spanish"],
                  answer=1, fact="Mandarin — around 940 million native speakers."),
             dict(q="How many seconds are in a day?", options=["46,400", "86,400", "106,400"],
                  answer=1, fact="86,400 — and now you'll see it everywhere."),
         ]),
    dict(key="geo_extremes_2", format="trivia", concept="geography", title="The Driest Place on Earth Has Never Seen Rain",
         hook="Three questions about the most extreme places on Earth. Most people fail.",
         questions=[
             dict(q="What is the driest non-polar place on Earth?", options=["Sahara Desert", "Atacama Desert", "Death Valley"],
                  answer=1, fact="Chile's Atacama — some weather stations have never recorded rain."),
             dict(q="Which country is completely surrounded by South Africa?", options=["Eswatini", "Lesotho", "Botswana"],
                  answer=1, fact="Lesotho — a whole country inside another country."),
             dict(q="Which is the longest north-to-south country?", options=["Argentina", "Chile", "Norway"],
                  answer=1, fact="Chile — about 4,300 km long but only 177 km wide on average."),
         ]),
    dict(key="riddles_3", format="riddle", concept="riddles", title="3 Riddles That Feel Illegal to Miss",
         hook="Number three feels illegal to miss.",
         questions=[
             dict(q="What has a neck but no head?", options=[], answer=-1, fact="A bottle."),
             dict(q="What invention lets you look right through a wall?", options=[], answer=-1, fact="A window."),
             dict(q="What belongs to you, but other people use it more than you?", options=[], answer=-1, fact="Your name."),
         ]),
    dict(key="wyr_food", format="wyr", concept="wyr", title="Would You Rather: Food Crimes Edition",
         hook="Food crimes. You must commit one.",
         questions=[
             dict(q="Never eat cheese again — or never eat chocolate again?", options=["No cheese", "No chocolate"],
                  answer=-1, fact=""),
             dict(q="Only spicy food forever — or only bland food forever?", options=["All spicy", "All bland"],
                  answer=-1, fact=""),
             dict(q="Pineapple on every pizza — or no pizza ever again?", options=["Pineapple forever", "No pizza"],
                  answer=-1, fact=""),
         ]),
    dict(key="wyr_travel", format="wyr", concept="wyr", title="Would You Rather: Travel Edition",
         hook="Pack your bags. You only get one of these.",
         questions=[
             dict(q="Free 5-star hotels forever — or free business-class flights forever?", options=["Hotels", "Flights"],
                  answer=-1, fact=""),
             dict(q="Live in a new country every year — or your dream city forever?", options=["New country yearly", "Dream city forever"],
                  answer=-1, fact=""),
             dict(q="See the past as a tourist — or see the future for one day?", options=["Visit the past", "Peek the future"],
                  answer=-1, fact=""),
         ]),
    dict(key="money_trivia_2", format="trivia", concept="money", title="The Penny Costs More Than a Penny",
         hook="Most people fail question two about the money in their wallet.",
         questions=[
             dict(q="What is US paper money actually made of?", options=["Paper", "Cotton and linen", "Plastic polymer"],
                  answer=1, fact="About 75 percent cotton, 25 percent linen — technically fabric."),
             dict(q="How much does it cost the US Mint to make one penny?", options=["Under 1 cent", "About 4 cents", "About 10 cents"],
                  answer=1, fact="Around 4 cents — every penny minted loses money."),
             dict(q="Which country issued the first paper money?", options=["Italy", "China", "Egypt"],
                  answer=1, fact="China — centuries before Europe caught on."),
         ]),
    dict(key="wyr_life", format="wyr", concept="wyr", title="Would You Rather: Life Edition",
         hook="These two choices start arguments. Which side are you on?",
         questions=[
             dict(q="Always be 10 minutes late — or always 20 minutes early?", options=["10 late", "20 early"],
                  answer=-1, fact=""),
             dict(q="Restart life with all your memories — or $10 million today?", options=["Restart + memories", "$10M today"],
                  answer=-1, fact=""),
             dict(q="Free coffee forever — or never hit traffic again?", options=["Free coffee", "No traffic"],
                  answer=-1, fact=""),
         ]),

    # ── US-ANCHORED (geo-tilt toward the high-RPM US Shorts pool) ──────────────
    # geo="us" quizzes are dormant until US_TILT=1 and are exempt from the
    # view-based retirement/weighting loop (they reach a smaller US-skewed
    # audience by design — raw global views would wrongly strangle them).
    dict(key="us_states_1", format="trivia", concept="geography", geo="us",
         title="Only 1 in 10 Get All 3 US State Questions",
         hook="Only 1 in 10 Americans get all three of these state questions right.",
         questions=[
             dict(q="Which US state is the largest by area?", options=["Texas", "Alaska", "California"],
                  answer=1, fact="Alaska — over twice the size of Texas."),
             dict(q="What is the capital of New York State?", options=["New York City", "Albany", "Buffalo"],
                  answer=1, fact="Albany — not New York City, which trips up almost everyone."),
             dict(q="Which US state has the most people?", options=["California", "Texas", "Florida"],
                  answer=0, fact="California — nearly 39 million residents."),
         ]),
    dict(key="us_presidents_1", format="trivia", concept="history", geo="us",
         title="The $100 Bill Question 90% Get Wrong",
         hook="Question three fools almost everyone.",
         questions=[
             dict(q="Who was the first US president?", options=["Benjamin Franklin", "George Washington", "Thomas Jefferson"],
                  answer=1, fact="George Washington — Franklin was never president."),
             dict(q="How many US presidents have been assassinated?", options=["2", "4", "6"],
                  answer=1, fact="Four — Lincoln, Garfield, McKinley, and Kennedy."),
             dict(q="Whose face is on the $100 bill?", options=["Benjamin Franklin", "Ulysses Grant", "Thomas Jefferson"],
                  answer=0, fact="Benjamin Franklin — and he was never a president."),
         ]),
    dict(key="us_landmarks_1", format="trivia", concept="geography", geo="us",
         title="3 US Landmark Questions Nobody Aces",
         hook="Most people miss question one about their own country.",
         questions=[
             dict(q="The Statue of Liberty was a gift from which country?", options=["United Kingdom", "France", "Spain"],
                  answer=1, fact="France — given to the US in 1886."),
             dict(q="Which US state is home to the Grand Canyon?", options=["Nevada", "Arizona", "Utah"],
                  answer=1, fact="Arizona — the canyon runs 277 miles and is a mile deep."),
             dict(q="How many presidents are carved into Mount Rushmore?", options=["3", "4", "5"],
                  answer=1, fact="Four — Washington, Jefferson, Roosevelt, and Lincoln."),
         ]),
    dict(key="us_money_1", format="trivia", concept="money", geo="us",
         title="The Dollar Bill Question Most People Fail",
         hook="Question two stumps nearly everyone.",
         questions=[
             dict(q="Which president is on the $1 bill?", options=["Washington", "Lincoln", "Jefferson"],
                  answer=0, fact="George Washington."),
             dict(q="Roughly how many $1 bills does the US print each day?", options=["1 million", "16 million", "500 million"],
                  answer=1, fact="About 16 million $1 bills every day."),
             dict(q="What building is on the back of the $10 bill?", options=["The White House", "US Treasury", "The Capitol"],
                  answer=1, fact="The US Treasury Building."),
         ]),
    dict(key="us_sports_1", format="trivia", concept="sports", geo="us",
         title="Only Real Sports Fans Get 3/3",
         hook="Question three fools even sports fans.",
         questions=[
             dict(q="How many players from one team are on a baseball field at once?", options=["9", "10", "11"],
                  answer=0, fact="Nine players."),
             dict(q="How long is an NFL field including both end zones?", options=["100 yards", "120 yards", "150 yards"],
                  answer=1, fact="120 yards — 100 plus two 10-yard end zones."),
             dict(q="Which US city's team has won the most NBA championships?", options=["Boston", "Los Angeles", "Chicago"],
                  answer=0, fact="Boston — the Celtics hold the most NBA titles."),
         ]),
    dict(key="us_geography_2", format="trivia", concept="geography", geo="us",
         title="3 US Geography Questions That Fool Adults",
         hook="Only one in ten Americans get all three of these right. Can you?",
         questions=[
             dict(q="What is the tallest mountain in the US?", options=["Mount Whitney", "Denali", "Mount Rainier"],
                  answer=1, fact="Denali in Alaska — 20,310 feet."),
             dict(q="Which US state has the most coastline?", options=["California", "Florida", "Alaska"],
                  answer=2, fact="Alaska — more than all other states combined."),
             dict(q="Which two US states border no other states?", options=["Alaska and Hawaii", "Hawaii and Florida", "Alaska and Maine"],
                  answer=0, fact="Alaska and Hawaii — the only two that touch no other state."),
         ]),
    dict(key="us_history_2", format="trivia", concept="history", geo="us",
         title="Can You Pass US History? 99% Can't",
         hook="Question two breaks most people. Think you can pass US history?",
         questions=[
             dict(q="In which year did the US declare independence?", options=["1776", "1789", "1812"],
                  answer=0, fact="1776 — July 4th."),
             dict(q="How many original colonies formed the United States?", options=["12", "13", "15"],
                  answer=1, fact="Thirteen."),
             dict(q="Which war caused the most US deaths overall?", options=["World War II", "The Civil War", "Vietnam"],
                  answer=1, fact="The Civil War — over 600,000 deaths."),
         ]),
    dict(key="us_food_1", format="trivia", concept="food", geo="us",
         title="3 American Food Facts That Sound Fake",
         hook="Three questions about American food. Nobody gets all three.",
         questions=[
             dict(q="Which US state grows the most potatoes?", options=["Iowa", "Idaho", "Ohio"],
                  answer=1, fact="Idaho — famous for it."),
             dict(q="What is the most-eaten meat in America?", options=["Beef", "Chicken", "Pork"],
                  answer=1, fact="Chicken — it passed beef years ago."),
             dict(q="About how many hot dogs do Americans eat on July 4th?", options=["15 million", "150 million", "1 billion"],
                  answer=1, fact="About 150 million hot dogs in a single day."),
         ]),
    # ── "Facts That Sound Fake" expansion (2026-07-15) ──────────────────────────
    # Assembled from question_bank.py generate -> blind-verify -> human-approved
    # questions. Same 3-fact format as us_food_1 (the 1,072-view breakout); only
    # the topic rotates. Titles are deliberately varied — identical titles are the
    # repetition pattern YouTube penalises.
    dict(key="facts_history_1", format="trivia", concept="history",
         title="3 History Facts That Sound Fake",
         hook="Three history facts that sound made up. Bet you doubt all three.",
         questions=[
             dict(q="What animal was still alive when the Pyramids were built?", options=["Woolly mammoth", "Saber-toothed tiger", "Dodo bird"],
                  answer=0, emoji="🦣", fact="Woolly mammoths survived on Wrangel Island until around 1650 BC — over a thousand years after the Great Pyramid was finished."),
             dict(q="In 1325, two Italian cities went to war over what stolen object?", options=["A wooden bucket", "A church bell", "A pig"],
                  answer=0, emoji="🪣", fact="The War of the Bucket — Modena and Bologna fought after soldiers stole a wooden bucket from a well."),
             dict(q="In 1814, eight people in London died from a flood of what?", options=["Beer", "Molasses", "Hot chocolate"],
                  answer=0, emoji="🍺", fact="The London Beer Flood — a brewery vat ruptured and released over 300,000 gallons into the streets."),
         ]),
    dict(key="facts_history_2", format="trivia", concept="history",
         title="History Class Left These 3 Out",
         hook="Your history teacher skipped these three. Watch to the end.",
         questions=[
             dict(q="Before becoming US President, Abraham Lincoln was an elite...", options=["Wrestler", "Bare-knuckle boxer", "Horse racer"],
                  answer=0, emoji="🤼", fact="Lincoln is in the National Wrestling Hall of Fame — he lost only one of roughly 300 matches."),
             dict(q="In 1952, Albert Einstein was offered the presidency of which country?", options=["Israel", "Germany", "Switzerland"],
                  answer=0, emoji="🧠", fact="Einstein was offered the presidency of Israel in 1952 but turned it down."),
             dict(q="Roughly 1 in how many men today are direct descendants of Genghis Khan?", options=["200", "2,000", "20,000"],
                  answer=0, emoji="🐎", fact="About 1 in 200 men worldwide carry the Y-chromosome linked to Genghis Khan."),
         ]),
    dict(key="facts_history_3", format="trivia", concept="history",
         title="3 Ancient Facts That Sound Made Up",
         hook="Three facts from the ancient world that sound completely fake.",
         questions=[
             dict(q="What did ancient Romans use as teeth whitener and mouthwash?", options=["Goat milk", "Urine", "Crushed charcoal"],
                  answer=1, emoji="🦷", fact="Urine — the ammonia in it acts as a natural whitening agent."),
             dict(q="What secret ingredient makes ancient Roman concrete last 2,000 years?", options=["Volcanic ash", "Olive oil", "Animal blood"],
                  answer=0, emoji="🌋", fact="Volcanic ash reacts with seawater to form minerals that make the concrete grow stronger over time."),
             dict(q="Cleopatra lived closer in time to which of these?", options=["The Moon landing", "Building the Pyramids", "The Trojan War"],
                  answer=0, emoji="🌙", fact="Cleopatra lived around 30 BC — closer to the 1969 Moon landing than to the Pyramids, built around 2560 BC."),
         ]),
    dict(key="facts_food_1", format="trivia", concept="food",
         title="3 Food Facts That Sound Fake",
         hook="Three food facts that sound fake. Number one starts an argument.",
         questions=[
             dict(q="Botanically speaking, which of these is actually a true berry?", options=["Banana", "Strawberry", "Raspberry"],
                  answer=0, emoji="🍌", fact="A berry comes from a flower with one ovary — so bananas qualify, but strawberries do not."),
             dict(q="Which part of a chili pepper is the hottest?", options=["The white pith", "The seeds", "The outer skin"],
                  answer=0, emoji="🌶️", fact="Capsaicin is concentrated in the white membrane holding the seeds, not the seeds themselves."),
             dict(q="What is the green wasabi in most Western restaurants actually made of?", options=["Horseradish", "Green mustard seeds", "Dyed ginger"],
                  answer=0, emoji="🍣", fact="Real wasabi is costly, so most places use dyed horseradish and mustard."),
         ]),
    dict(key="facts_food_2", format="trivia", concept="food",
         title="You Won't Believe These 3 Food Facts",
         hook="Three food facts you won't believe are actually true.",
         questions=[
             dict(q="Why did Britain spread the rumor that carrots improve night vision?", options=["To hide secret radar tech", "To boost carrot sales", "To cure a vitamin shortage"],
                  answer=0, emoji="📡", fact="In WWII the RAF invented it to explain night kills without revealing radar."),
             dict(q="Why do fresh apples float in water?", options=["They are 25% air", "They have oily skin", "Their seeds hold gas"],
                  answer=0, emoji="🍎", fact="About 25% of an apple's volume is air pockets between the cells."),
             dict(q="What test is used to check if fresh cranberries are ripe?", options=["They bounce them", "They float them in oil", "They squeeze them for a pop"],
                  answer=0, emoji="🔴", fact="Ripe cranberries have air pockets that make them springy, so farmers sort them by bouncing."),
         ]),
    dict(key="facts_animals_1", format="trivia", concept="animals",
         title="3 Animal Facts That Sound Fake",
         hook="One in ten people get all three of these animal facts.",
         questions=[
             dict(q="Which animal naturally produces cube-shaped poop?", options=["Wombat", "Koala", "Sloth"],
                  answer=0, emoji="🧊", fact="Wombats are the only animals with cube-shaped droppings — it stops them rolling off rocks used to mark territory."),
             dict(q="An ostrich's eye is bigger than its what?", options=["Brain", "Heart", "Stomach"],
                  answer=0, emoji="👁️", fact="An ostrich's eye is larger than its whole brain."),
             dict(q="What color do reindeer eyes turn in winter?", options=["Blue", "Green", "Red"],
                  answer=0, emoji="🦌", fact="Reindeer eyes shift from gold in summer to blue in winter to capture more light."),
         ]),
]

# ── Narration builder (deterministic — no LLM, no hallucinated answers) ──────
_LEAD_QUALIFIER = re.compile(r"^(The|A|An|About|Around|Roughly|Nearly|Over|Under|Every|All)\b")


def _spoken(option) -> str:
    """An option is written for the CARD ("The doubling penny") and then read out
    mid-sentence. The burned-in captions echo the spoken text, so the card's
    capital leaks into a sentence as "It's The doubling penny!".

    Lowercase a leading qualifier only. A proper noun ("Saturn", "Alaska and
    Hawaii") keeps its capital, which is why this matches a fixed word list
    rather than blindly lowercasing the first letter.
    """
    s = str(option)
    return s[0].lower() + s[1:] if _LEAD_QUALIFIER.match(s) else s


def build_segments(quiz):
    """Returns [(kind, qi, text)] — kinds: intro, ask, reveal, outro.
    The renderer paces phases by each segment's word share of the narration."""
    # Intro is the hook and nothing else. Every second before question 1 is a
    # second the viewer can swipe, and the swipe decision happens in the first
    # one or two — "Count your score" used to buy a full extra beat of nothing.
    segs = [("intro", -1, quiz["hook"])]
    for i, q in enumerate(quiz["questions"], 1):
        if quiz["format"] == "trivia":
            opts = q["options"]
            # No spoken "three... two... one..." any more — a silent beep
            # countdown is spliced in before each reveal (insert_countdown_gaps +
            # mix_quiz_sfx), which reads far less robotic than a voice counting.
            segs.append(("ask", i - 1,
                         f"Question {i}. {q['q']} "
                         f"{_spoken(opts[0])}, {_spoken(opts[1])}, or {_spoken(opts[2])}?"))
            segs.append(("reveal", i - 1, f"It's {_spoken(opts[q['answer']])}! {q['fact']}"))
        elif quiz["format"] == "riddle":
            segs.append(("ask", i - 1, f"Riddle {i}. {q['q']}"))
            segs.append(("reveal", i - 1, f"The answer: {q['fact']}"))
        else:  # wyr — pure poll, no reveal
            opts = q["options"]
            segs.append(("ask", i - 1,
                         f"Round {i}. Would you rather: {_spoken(opts[0])}... "
                         f"or {_spoken(opts[1])}? "
                         f"Think... three... two... one... lock it in."))
    # Outro is 3 words on purpose: spoken tail after the last reveal is pure
    # retention drain (the expansion gate is average view duration), and the
    # comment ask is the one CTA that feeds the first-hour engagement signal.
    # "Follow" lives in the description + pinned comment instead.
    segs.append(("outro", -1,
                 "Comment your score!"
                 if quiz["format"] != "wyr" else
                 "Comment your picks!"))
    return segs


def _narration(quiz):
    return " ".join(s[2] for s in build_segments(quiz))


# ── Emoji artwork ─────────────────────────────────────────────────────────────
# Always images, never glyphs: the Actions runner ships no emoji font, so emoji
# drawn as text render as tofu boxes in every video CI builds while looking fine
# on Windows.
_EMOJI_DIR   = Path(__file__).parent / "assets" / "emoji"
_EMOJI_CACHE = _EMOJI_DIR / "cache"
_TWEMOJI     = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{}.png"
_emoji_memo: dict = {}


def emoji_image(char: str, concept: str = "default"):
    """PIL image for a question's emoji, falling back to the bundled topic icon.

    Per-question emoji (a question about the Moon gets a moon) can be any
    codepoint, so the artwork is fetched from the Twemoji CDN on first use and
    cached on disk. Any failure — offline, odd codepoint — falls back to the
    bundled set, so a render never depends on the network.
    """
    key = (char or "", concept)
    if key in _emoji_memo:
        return _emoji_memo[key]

    img = None
    if char:
        code = "-".join(f"{ord(c):x}" for c in char if ord(c) not in (0xFE0F, 0x200D))
        try:
            _EMOJI_CACHE.mkdir(parents=True, exist_ok=True)
            path = _EMOJI_CACHE / f"{code}.png"
            if not path.exists():
                import urllib.request
                req = urllib.request.Request(_TWEMOJI.format(code),
                                             headers={"User-Agent": "Mozilla/5.0"})
                path.write_bytes(urllib.request.urlopen(req, timeout=15).read())
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            print(f"[Emoji] '{char}' unavailable ({e}) — using the {concept} icon")
            img = None

    if img is None:
        p = _EMOJI_DIR / f"{concept}.png"
        if not p.exists():
            p = _EMOJI_DIR / "default.png"
        try:
            img = Image.open(p).convert("RGBA")
        except Exception:
            img = None

    _emoji_memo[key] = img
    return img


def segment_starts(segs, duration, marks=None):
    """Absolute start time (seconds) of each segment, plus whether the timings
    are real.

    Word share is a bad proxy for speech time: a "Three... two... one..."
    countdown runs ~0.75s/word against ~0.47s/word for plain narration, so the
    estimate drifts up to 4s out over a 60s script — the picture and captions
    end up trailing the voice. edge-tts SentenceBoundary marks give the true
    offsets, and because segments are built from whole sentences, a segment
    boundary always lands on a sentence boundary.

    Marks can be absent (some voices/versions emit none), so the word-share
    path stays as a fallback. Returns (starts, is_real).
    """
    words = [max(1, len(s[2].split())) for s in segs]
    total = sum(words) or 1

    def word_share():
        out, acc = [], 0.0
        for w in words:
            out.append(acc)
            acc += duration * w / total
        return out

    if not marks:
        return word_share(), False

    # cumulative word index at which each segment begins
    starts_at, acc = [], 0
    for w in words:
        starts_at.append(acc)
        acc += w

    real, cum = {}, 0
    for off, _sd, txt in marks:
        for i, sw in enumerate(starts_at):
            if i not in real and abs(sw - cum) <= 2:   # tolerate minor tokenisation drift
                real[i] = off
        cum += len(txt.split())

    got = [real.get(i) for i in range(len(segs))]
    # any gap, any backwards step, or an overrun means the alignment is not
    # trustworthy — fall back rather than ship worse sync than we started with
    if any(g is None for g in got):
        return word_share(), False
    if any(got[i] > got[i + 1] for i in range(len(got) - 1)):
        return word_share(), False
    if got[-1] > duration:
        return word_share(), False
    return got, True


# ── Silent beep countdown ────────────────────────────────────────────────────
# The spoken "three... two... one..." was replaced by a real silent think-window
# with synced beeps. GAP is the length of that window; both the audio splice
# below and the beep placement in mix_quiz_sfx read this one constant so they
# cannot drift. Tune GAP / the beep pattern to taste.
COUNTDOWN_GAP = 2.5


def insert_countdown_gaps(audio_path, segs, marks, duration):
    """Splice a silent GAP-second think-window into the voice audio immediately
    before every reveal, and shift the sentence marks to match. Returns
    (new_duration, shifted_marks).

    MUST run right after the voiceover, before seg_starts and the chart are
    computed, so the whole render is built against the longer, gapped audio.
    mix_quiz_sfx later fills each gap with beeps in the same [reveal-GAP, reveal]
    window. Falls back to a no-op (returns the inputs unchanged) on any error.
    """
    if duration <= 0 or not any(s[0] == "reveal" for s in segs):
        return duration, marks
    starts, _real = segment_starts(segs, duration, marks)
    cuts = sorted(starts[i] for i, s in enumerate(segs)
                  if s[0] == "reveal" and 0.0 < starts[i] < duration)
    if not cuts:
        return duration, marks
    try:
        import numpy as np, os as _os
        from moviepy.editor import AudioFileClip, concatenate_audioclips
        from moviepy.audio.AudioClip import AudioClip
        # Concatenate real audio slices with silence clips and write through the
        # ffmpeg audio-writer. (Do NOT use to_soundarray — moviepy 1.0.3 feeds a
        # generator to np.vstack, which numpy 2.x rejects; the writer path is fine.)
        voice = AudioFileClip(audio_path)
        sr    = int(voice.fps) or 44100
        nch   = getattr(voice, "nchannels", 2) or 2
        def _sil(t):
            t = np.atleast_1d(t)
            return np.zeros((len(t), nch)) if nch > 1 else np.zeros(len(t))
        pieces, prev = [], 0.0
        for c in cuts:
            c = min(max(c, prev), voice.duration)
            pieces.append(voice.subclip(prev, c))
            pieces.append(AudioClip(_sil, duration=COUNTDOWN_GAP, fps=sr))
            prev = c
        pieces.append(voice.subclip(prev, voice.duration))
        gapped = concatenate_audioclips(pieces)
        out    = audio_path + ".gap.mp3"
        gapped.write_audiofile(out, fps=sr, logger=None)
        new_dur = gapped.duration
        gapped.close(); voice.close()
        _os.replace(out, audio_path)
    except Exception as e:
        print(f"[Gap] countdown gap insertion skipped ({e})")
        return duration, marks
    shifted = [(off + COUNTDOWN_GAP * sum(1 for c in cuts if c <= off + 1e-6), d, txt)
               for off, d, txt in marks]
    print(f"[Gap] {len(cuts)} x {COUNTDOWN_GAP}s countdown gaps -> {new_dur:.1f}s")
    return new_dur, shifted


# ── Generic quiz renderer ─────────────────────────────────────────────────────
def render_quiz(out_path, accent, target_duration, fps=24, quiz=None, seg_starts=None,
                bg_image=None):
    ah   = _hex(accent)
    segs = build_segments(quiz)
    words = [max(1, len(s[2].split())) for s in segs]
    total = sum(words)
    # cumulative fraction boundaries per segment. seg_starts (real TTS sentence
    # offsets) keeps the reveal on the same frame as the spoken answer; without
    # them we fall back to word share, which lags the voice by seconds.
    if seg_starts and len(seg_starts) == len(segs) and target_duration > 0:
        bounds = [
            (seg_starts[i + 1] if i + 1 < len(segs) else target_duration) / target_duration
            for i in range(len(segs))
        ]
        bounds[-1] = 1.0
    else:
        bounds, acc = [], 0.0
        for w in words:
            acc += w / total
            bounds.append(acc)
    n_frames = int(target_duration * fps)

    def seg_at(frac):
        for i, b in enumerate(bounds):
            if frac <= b:
                start = bounds[i - 1] if i else 0.0
                return i, (frac - start) / max(b - start, 1e-9)
        return len(segs) - 1, 1.0

    def wrap(s, width=26):
        return "\n".join(textwrap.wrap(s, width))

    fig = plt.figure(figsize=(W_PX / DPI, H_PX / DPI), facecolor=BG)
    ax  = fig.add_subplot(111)

    # Photo background. build_video lays this same photo across the full
    # 1080x1920 frame and drops the chart on top of it, so the chart must carry
    # exactly the slice of the photo that will sit behind it — otherwise the
    # two copies disagree and you see a seam. That slice is CHART_BAND.
    kb = None
    if bg_image:
        try:
            from backgrounds import kb_base
            kb = kb_base(bg_image)
        except Exception as _be:
            print(f"[Anim] photo background skipped: {_be}")
            kb = None

    _band_cache: dict = {}

    def paint_bg(t):
        """Redraw the drifting photo slice for time t. Must go through the same
        kb_frame as build_video, or the two copies of the photo would disagree
        and the seam between them would reopen.

        Kept in uint8 — converting to float here built a 34MB array per frame.
        """
        from backgrounds import kb_frame
        import numpy as _np
        frame_img = kb_frame(kb, t, target_duration)
        key = id(frame_img)                       # kb_frame reuses the object per step
        band = _band_cache.get(key)
        if band is None:
            top, bot = CHART_BAND
            band = _np.asarray(
                frame_img.crop((0, top, frame_img.width, bot))
                         .resize((W_PX, H_PX), Image.BILINEAR))
            _band_cache.clear()
            _band_cache[key] = band
        fig.images.clear()
        fig.figimage(band, 0, 0, zorder=-10, origin="upper")

    # Artwork per QUESTION, not per topic: a question about the Moon rolls a moon
    # down the bar, the next one rolls something else. Falls back to the topic
    # icon when a question carries no emoji of its own.
    _concept = (quiz or {}).get("concept", "default")

    def art_for(q):
        return emoji_image((q or {}).get("emoji", ""), _concept)

    import matplotlib.patches as mpatches

    # Solid cards, not translucent panels. Text sitting straight on a photo is
    # unreadable (white lettering on the Eiffel Tower's ironwork disappears), so
    # every word the viewer must read sits on an opaque card. This is the whole
    # reason photo backgrounds work for the channels doing this format well.
    CARD  = "#FFFFFF"
    INK   = "#12121C"
    RIGHT = "#22C55E"    # correct answer — green reads as "correct" instantly
    DIMC  = "#9CA3AF"

    def card(x0, y, w, h, facecolor, edgecolor, lw=3, z=3):
        ax.add_patch(mpatches.FancyBboxPatch(
            (x0, y - h / 2), w, h, transform=ax.transAxes,
            boxstyle="round,pad=0.010,rounding_size=0.030",
            facecolor=facecolor, edgecolor=edgecolor, linewidth=lw, zorder=z))

    def draw_option(y, label, text, state, h=0.105):
        """Full-width answer card. state: normal|correct|dim"""
        face = RIGHT if state == "correct" else (CARD if state != "dim" else "#E5E7EB")
        tcol = "white" if state == "correct" else (INK if state != "dim" else DIMC)
        # a green badge on the green "correct" card is invisible — darken it
        badge = "#15803D" if state == "correct" else (ah if state != "dim" else DIMC)
        card(0.045, y, 0.91, h, face, badge, lw=4 if state == "correct" else 3)
        # letter badge
        card(0.075, y, 0.105, h * 0.66, badge, badge, lw=1, z=4)
        ax.text(0.1275, y, label, transform=ax.transAxes, color="white",
                fontsize=30, ha="center", va="center", fontweight="bold", zorder=5)
        ax.text(0.575, y, wrap(text, 20), transform=ax.transAxes, color=tcol,
                fontsize=27, ha="center", va="center", fontweight="bold", zorder=5)

    def roller(x, y, travelled, colour, marker):
        """The marker rolls: it spins like a wheel by exactly the distance it has
        travelled, so it reads as physically rolling down the bar rather than
        sliding. travelled is in axes-x units."""
        if marker is None:
            ax.plot([x], [y], transform=ax.transAxes, marker="o", markersize=30,
                    color="#FDE047", markeredgecolor=colour, markeredgewidth=3, zorder=7)
            return
        from matplotlib.offsetbox import OffsetImage, AnnotationBbox
        from PIL import ImageDraw
        import numpy as _np
        r_axes = 0.030                                  # marker radius in axes-x units
        deg    = -(travelled / r_axes) * (180.0 / _np.pi)   # roll without slipping
        img    = marker.rotate(deg, resample=Image.BICUBIC, expand=False)
        # Twemoji "place" glyphs (statue, tower) carry their own square sky
        # background — rolling a square tile looks broken, so clip to a disc.
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, img.size[0] - 1, img.size[1] - 1), fill=255)
        img = img.copy()
        img.putalpha(Image.composite(img.getchannel("A"), mask, mask))
        ab = AnnotationBbox(OffsetImage(_np.asarray(img), zoom=0.95),
                            (x, y), xycoords=ax.transAxes,
                            frameon=False, box_alignment=(0.5, 0.5), zorder=8)
        ax.add_artist(ab)

    def animate(frame):
        ax.cla()
        if kb is not None:
            paint_bg(frame / fps)      # drifting photo, redrawn each frame
            ax.patch.set_alpha(0)      # let it show through the axes
        else:
            ax.set_facecolor(BG)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        si, sp_frac = seg_at(frame / max(1, n_frames - 1))
        kind, qi, _ = segs[si]

        if kind == "intro":
            # The hook itself, big and immediate — it is the only thing standing
            # between the viewer and question 1, so it had better be the claim
            # that earns the watch, not branding.
            hk = wrap(quiz["hook"], 17)
            card(0.045, 0.62, 0.91, 0.16 + 0.062 * hk.count("\n"), CARD, "white", lw=0)
            ax.text(0.5, 0.62, hk, transform=ax.transAxes, color=INK,
                    fontsize=40, ha="center", va="center", fontweight="bold", zorder=5)
            ax.text(0.5, 0.38, "3 QUESTIONS", transform=ax.transAxes, color="white",
                    fontsize=44, ha="center", va="center", fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.40", facecolor=ah, edgecolor="none"))
            return []
        if kind == "outro":
            # A "would you rather" has no score — the voice says "Comment your
            # picks!", so the card must not demand a score out of 3.
            _wyr = quiz["format"] == "wyr"
            card(0.045, 0.52, 0.91, 0.20, CARD, "white", lw=0)
            ax.text(0.5, 0.565, "YOUR PICKS?" if _wyr else "YOUR SCORE?",
                    transform=ax.transAxes, color=INK,
                    fontsize=46, ha="center", va="center", fontweight="bold", zorder=5)
            ax.text(0.5, 0.470, "Comment them below" if _wyr else "Comment it below",
                    transform=ax.transAxes, color=ah,
                    fontsize=26, ha="center", va="center", fontweight="bold", zorder=5)
            return []

        q = quiz["questions"][qi]
        # round chip
        ax.text(0.5, 0.965, f"{'ROUND' if quiz['format'] == 'wyr' else 'QUESTION'} {qi + 1} OF 3",
                transform=ax.transAxes, color="white", fontsize=20, ha="center",
                va="center", fontweight="bold", zorder=6,
                bbox=dict(boxstyle="round,pad=0.45", facecolor=ah, edgecolor="none"))

        # question on a solid white card — the single most important thing to read
        qtext = wrap(q["q"], 20)
        qlines = qtext.count("\n") + 1
        qh = 0.055 + 0.052 * qlines
        card(0.045, 0.845, 0.91, qh, CARD, "white", lw=0)
        ax.text(0.5, 0.845, qtext, transform=ax.transAxes, color=INK,
                fontsize=34, ha="center", va="center", fontweight="bold", zorder=5)

        # The emoji rides the card's top-left EDGE like a sticker. Sitting it
        # inside the card put it straight on top of the first line of the
        # question ("[burger]Which US state grows..."), which is unreadable — the
        # question text is centred and runs nearly the full width of the card, so
        # there is no room inside it for anything else.
        _art = art_for(q)
        if _art is not None:
            from matplotlib.offsetbox import OffsetImage, AnnotationBbox
            import numpy as _np
            ax.add_artist(AnnotationBbox(
                OffsetImage(_np.asarray(_art), zoom=0.8),
                (0.115, 0.845 + qh / 2), xycoords=ax.transAxes,
                frameon=False, box_alignment=(0.5, 0.5), zorder=6))

        if quiz["format"] == "wyr":
            draw_option(0.575, "1", q["options"][0], "normal", h=0.11)
            ax.text(0.5, 0.465, "— OR —", transform=ax.transAxes, color=ah,
                    fontsize=22, ha="center", va="center", fontweight="bold", zorder=5)
            draw_option(0.355, "2", q["options"][1], "normal", h=0.11)
            # Clear of the countdown bar (0.185) and the ~0.042-tall marker riding
            # it — at 0.225 the chip buried the rolling emoji behind itself.
            ax.text(0.5, 0.272, "COMMENT  1  OR  2", transform=ax.transAxes,
                    color="white", fontsize=19, ha="center", va="center",
                    fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="#232340", edgecolor=ah))
        elif quiz["format"] == "riddle":
            # The riddle's answer is the payoff of the whole video and was the one
            # piece of must-read text still drawn straight onto the photo — it
            # vanished into a busy background. It gets a card like everything else.
            if kind == "reveal":
                atxt = wrap(q["fact"], 18)
                card(0.045, 0.475, 0.91, 0.13 + 0.058 * atxt.count("\n"),
                     RIGHT, RIGHT, lw=0)
                ax.text(0.5, 0.475, atxt, transform=ax.transAxes, color="white",
                        fontsize=36, ha="center", va="center", fontweight="bold", zorder=5)
            else:
                card(0.045, 0.475, 0.91, 0.20, CARD, "white", lw=0)
                ax.text(0.5, 0.475, "?", transform=ax.transAxes, color=ah,
                        fontsize=96, ha="center", va="center", fontweight="bold", zorder=5)
        else:  # trivia
            ys = (0.615, 0.475, 0.335)
            for oi, y in enumerate(ys):
                state = ("correct" if oi == q["answer"] else "dim") if kind == "reveal" else "normal"
                draw_option(y, "ABC"[oi], q["options"][oi], state, h=0.115)
            if kind == "reveal" and q["fact"]:
                card(0.045, 0.185, 0.91, 0.10, "#111827", ah, lw=2)
                ax.text(0.5, 0.185, wrap(q["fact"], 40), transform=ax.transAxes,
                        color="white", fontsize=19, ha="center", va="center", zorder=5)

        # countdown bar during the ask phase — chunky, with a smiley riding the
        # fill, so the time pressure is legible at a glance on a phone
        if kind == "ask":
            left = 1.0 - sp_frac
            x0, x1, ybar = 0.09, 0.91, 0.185
            colour = "#EF4444" if left < 0.3 else ah
            ax.plot([x0, x1], [ybar, ybar], transform=ax.transAxes,
                    color="#E5E7EB", linewidth=30, solid_capstyle="round", zorder=3)
            if left > 0.02:
                ax.plot([x0, x0 + (x1 - x0) * left], [ybar, ybar], transform=ax.transAxes,
                        color=colour, linewidth=30, solid_capstyle="round", zorder=4)
            # the marker starts at the right and rolls left as the time drains
            mx = x0 + (x1 - x0) * max(left, 0.0)
            roller(mx, ybar, travelled=(x1 - mx), colour=colour, marker=art_for(q))
        return []

    ani = animation.FuncAnimation(fig, animate, frames=n_frames,
                                  interval=1000 / fps, blit=False)
    ani.save(out_path, writer="ffmpeg", fps=fps, dpi=DPI,
             savefig_kwargs={"facecolor": BG})
    plt.close(fig)
    print(f"[Anim] {quiz['key']}: {n_frames/fps:.1f}s @ {fps}fps (quiz/{quiz['format']})")


# ── Pipeline interfaces (same names as chartshock's charts.py) ───────────────
# "Would You Rather" (format="wyr") is retired as of 2026-07-14: it is a pure
# opinion poll with no reveal, and it is the channel's worst format — "Impossible
# Powers" held 0:14 average view duration against a 0:34 channel average, and the
# format has never produced a video that the Shorts feed pushed. The questions are
# left in QUIZZES so the format can be switched back on by flipping this flag;
# everything below (ANIMATIONS, RENDERERS, CONCEPT_PLAYLISTS, US_KEYS, the dynamic
# Gemini slot) is built from the filtered list, so the rotation cannot pick a WYR.
WYR_ENABLED = False
if not WYR_ENABLED:
    QUIZZES = [q for q in QUIZZES if q["format"] != "wyr"]


# ── ajabgajab: replace the US quiz set with India "3-fact" reels built from the
# approved question bank. Each 3 approved facts of a pillar become one reel.
# Concepts are mapped onto the existing playlist/background-scene keys so the
# rest of the file (playlists, CONCEPT_QUERY scenes) needs no changes.
def _india_quizzes():
    import json as _json
    from pathlib import Path as _Path
    from collections import OrderedDict as _OD
    _CMAP = {"india_gk": "geography", "movies": "history", "cricket": "sports",
             "science": "tech", "history": "history", "geography": "geography",
             "food": "food", "world": "geography", "animals": "animals",
             "mythology": "history", "space": "space", "technology": "tech",
             "sports": "sports"}
    try:
        _fs = _json.loads((_Path(__file__).parent / "question_bank.json")
                          .read_text(encoding="utf-8")).get("questions", [])
    except Exception as _e:
        print(f"[India] bank load failed: {_e}")
        return []
    _fs = [f for f in _fs if f.get("status") == "approved" and len(f.get("options") or []) == 3]
    if not _fs:
        return []
    # ONE fact per reel (~25-30s) for max-reach Shorts. The question itself is the
    # curiosity title (localised to Hinglish at render). Keyed per concept+index so
    # the ledger/dedup stays stable as the bank grows.
    _seen, _idx, _out = {}, {}, []
    for f in _fs:
        _c = f.get("concept", "world")
        _idx[_c] = _idx.get(_c, 0) + 1
        _out.append(dict(
            key=f"in_{_c}_{_idx[_c]}", format="trivia", concept=_CMAP.get(_c, "geography"),
            title=f["q"],
            hook="Only one in ten gets this right.",
            questions=[dict(q=f["q"], options=f["options"], answer=f["answer"],
                            fact=f.get("fact", ""), emoji=f.get("emoji", ""),
                            image_query=f.get("image_query", ""))]))
    return _out


_india = _india_quizzes()
if _india:
    QUIZZES = _india
    print(f"[India] loaded {len(QUIZZES)} 3-fact reels from the bank")

_GROUP_PLAYLISTS = {
    "space": "Space Quizzes", "trick": "Trick Questions", "animals": "Animal Quizzes",
    "body": "Human Body Quizzes", "geography": "Geography Quizzes", "history": "History Quizzes",
    "price": "Guess the Price", "money": "Money Quizzes", "riddles": "Riddles",
    "wyr": "Would You Rather", "tech": "Tech Quizzes", "food": "Food Quizzes",
    "odds": "Odds & Probability", "sports": "Sports Quizzes",
    "automotive": "Car Quizzes",
}
CONCEPT_PLAYLISTS = dict(_GROUP_PLAYLISTS)
CONCEPT_PLAYLISTS.update({q["key"]: _GROUP_PLAYLISTS[q["concept"]] for q in QUIZZES})
DEFAULT_PLAYLIST = "Daily Brain Quizzes"

ANIMATIONS = {
    q["key"]: {
        "topic":       q["title"],
        "title":       q["title"],
        "description": (f"{q['hook']} Three rounds — count your score and drop it in the "
                        "comments. A new quiz every day. "
                        "Answers verified before posting; general knowledge for entertainment."),
        "tags": ["quiz", "trivia", "brain teaser", "riddles", "test your knowledge",
                 "shorts", "challenge", q["concept"]],
        "cta":         "Follow for a new quiz every day.",
        "narration":   _narration(q),
        "concept":     q["concept"],
    }
    for q in QUIZZES
}

RENDERERS = {q["key"]: partial(render_quiz, quiz=q) for q in QUIZZES}

# US-anchored topics. Gated behind US_TILT=1 (pick_animation_type) and exempt from
# retirement (performance.retired_keys): they reach a smaller US-skewed audience by
# design, so global numbers would wrongly kill them before the geo tilt can pay off.
US_KEYS = {q["key"] for q in QUIZZES if q.get("geo") == "us"}


def compute_anim_numbers(anim_key: str) -> dict:
    """Empty on purpose: narration is deterministic — the pipeline skips the
    LLM step entirely when no numbers are provided."""
    return {}


# ── Dynamic slot: Gemini-generated Would You Rather ──────────────────────────
# WYR is pure opinion — no facts to hallucinate — so this is the ONE place an
# LLM may write content at runtime. Trivia answers stay hand-verified forever.
GEMINI_WYR_KEY = "wyr_fresh_daily"
_BANNED = ("kill", "die", "death", "sex", "drug", "politic", "religio", "race",
           "gun", "suicide", "naked", "war crime")


def hydrate_dynamic(anim_key: str, gemini_key: str):
    """If the rotation picked the dynamic WYR slot and a Gemini key exists,
    generate 3 fresh dilemmas. Returns {'meta':..., 'renderer':...} or None
    (None -> the static fallback questions in QUIZZES are used)."""
    if not WYR_ENABLED or anim_key != GEMINI_WYR_KEY or not gemini_key:
        return None
    import json as _j
    from google import genai
    client = genai.Client(api_key=gemini_key)
    prompt = (
        'Write 3 fresh "would you rather" dilemmas for a general audience. '
        "Rules: purely subjective (no factual answers), brand-safe, no politics/"
        "religion/violence/adult themes, each option at most 8 words, genuinely "
        "hard to choose, funny or thought-provoking. Return ONLY JSON: "
        '[{"q": "Would you rather ...?", "options": ["...", "..."]}] with exactly 3 items.'
    )
    for model in ("gemini-flash-lite-latest", "gemini-flash-latest"):
        try:
            r = client.models.generate_content(
                model=model, contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=1.0, max_output_tokens=600,
                    response_mime_type="application/json"))
            items = _j.loads(r.text.strip())
            assert len(items) == 3
            qs = []
            for it in items:
                o = it["options"]
                assert len(o) == 2 and all(1 <= len(x.split()) <= 9 for x in o)
                blob = (it["q"] + " " + o[0] + " " + o[1]).lower()
                assert not any(b in blob for b in _BANNED)
                q_text = it["q"].strip()
                q_text = q_text[len("would you rather"):].strip(" :,") if q_text.lower().startswith("would you rather") else q_text
                qs.append(dict(q=q_text, options=[o[0].strip(), o[1].strip()],
                               answer=-1, fact=""))
            quiz = dict(key=GEMINI_WYR_KEY, format="wyr", concept="wyr",
                        title="Would You Rather: Today's 3 Impossible Picks",
                        hook="Three fresh dilemmas. Pick a side on all three.",
                        questions=qs)
            print(f"[Dynamic] fresh WYR generated by {model}")
            return {
                "meta": {
                    "title":     quiz["title"],
                    "topic":     quiz["title"],
                    "narration": _narration(quiz),
                },
                "renderer": partial(render_quiz, quiz=quiz),
                "quiz": quiz,
            }
        except Exception as e:
            print(f"[Dynamic] {model} failed ({str(e)[:80]}) — trying next")
    print("[Dynamic] all models failed — using static fallback questions")
    return None


# Static fallback occupies the dynamic slot in the normal rotation
if WYR_ENABLED:
    QUIZZES.append(dict(
        key=GEMINI_WYR_KEY, format="wyr", concept="wyr",
        title="Would You Rather: Impossible Picks",
        hook="Two options, one choice, and no right answer. What do you pick?",
        questions=[
            dict(q="Always say what you think — or never speak again?", options=["Total honesty", "Total silence"], answer=-1, fact=""),
            dict(q="Re-live your best day weekly — or get one extra hour daily?", options=["Best day rerun", "25-hour days"], answer=-1, fact=""),
            dict(q="Be famous for something embarrassing — or unknown for something great?", options=["Embarrassing fame", "Unknown greatness"], answer=-1, fact=""),
        ]))
    CONCEPT_PLAYLISTS[GEMINI_WYR_KEY] = _GROUP_PLAYLISTS["wyr"]
    ANIMATIONS[GEMINI_WYR_KEY] = {
        "topic": "Would You Rather: Impossible Picks",
        "title": "Would You Rather: Impossible Picks",
        "description": ("Three impossible choices — pick a side on all three and defend it "
                        "in the comments. A new quiz every day."),
        "tags": ["would you rather", "quiz", "challenge", "shorts", "trivia", "hard choices"],
        "cta": "Follow for a new quiz every day.",
        "narration": _narration(QUIZZES[-1]),
        "concept": "wyr",
    }
    RENDERERS[GEMINI_WYR_KEY] = partial(render_quiz, quiz=QUIZZES[-1])


# ── Synthesized SFX: ticking under countdowns, ding on reveals ───────────────
# Pure sine synthesis — zero copyright surface. Timing uses the same
# word-share model as the renderer, so sound and visuals stay aligned.
def mix_quiz_sfx(audio_path: str, anim_key: str, duration: float, seg_starts=None) -> None:
    import numpy as np, wave, tempfile, os
    quiz = next((q for q in QUIZZES if q["key"] == anim_key), None)
    if not quiz or duration <= 0:
        return
    segs   = build_segments(quiz)
    words  = [max(1, len(s[2].split())) for s in segs]
    total  = sum(words)
    sr     = 44100
    track  = np.zeros(int(duration * sr), dtype=np.float32)

    def add(sound, t0):
        i = int(t0 * sr)
        j = min(i + len(sound), len(track))
        if i < len(track):
            track[i:j] += sound[: j - i]

    def tone(freq, secs, vol, decay=8.0):
        t = np.linspace(0, secs, int(sr * secs), False)
        return (np.sin(2 * np.pi * freq * t) * np.exp(-decay * t) * vol).astype(np.float32)

    use_real = bool(seg_starts) and len(seg_starts) == len(segs)
    acc = 0.0
    for i, ((kind, _qi, _txt), w) in enumerate(zip(segs, words)):
        if use_real:
            s0 = seg_starts[i]
            s1 = seg_starts[i + 1] if i + 1 < len(seg_starts) else duration
        else:
            s0 = acc
            s1 = acc + duration * w / total
        seg_len = max(s1 - s0, 0.0)
        if kind == "ask":
            # Beeps fill the silent think-window at the END of the ask (the last
            # GAP seconds before the reveal), where insert_countdown_gaps spliced
            # in silence. Louder than the old ticks — no speech to compete with.
            # Three ticks, then a higher "go" leading into the reveal ding.
            g0 = max(s0, s1 - COUNTDOWN_GAP)
            for k in range(3):
                add(tone(1200, 0.09, 0.30, decay=24), g0 + 0.15 + k * 0.55)
            add(tone(1650, 0.16, 0.32, decay=10), s1 - 0.16)
        elif kind == "reveal":
            add(tone(880, 0.12, 0.22, decay=12), s0)          # ding
            add(tone(1320, 0.25, 0.18, decay=8), s0 + 0.10)   # sparkle
        acc = s1

    fd, sfx_wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    pcm = (np.clip(track, -1, 1) * 32767).astype(np.int16)
    with wave.open(sfx_wav, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    try:
        from moviepy.editor import AudioFileClip, CompositeAudioClip
        voice = AudioFileClip(audio_path)
        sfx   = AudioFileClip(sfx_wav)
        mixed = CompositeAudioClip([voice, sfx.subclip(0, min(duration, sfx.duration))])
        out = audio_path + ".sfx.mp3"
        mixed.write_audiofile(out, fps=sr, logger=None)
        voice.close(); sfx.close()
        os.replace(out, audio_path)
        print(f"[SFX] ticks + reveal dings mixed in")
    finally:
        try:
            os.remove(sfx_wav)
        except OSError:
            pass
