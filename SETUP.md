> **2026-10-28:** the Hinglish quiz pipeline this checklist launched (pipeline_animated.py, facts.yml,
> compilation.yml) was retired and removed; the channel runs only `katha/` now. It is still in git
> history (before this commit). Sections 1-6 still describe the accounts, keys and `auth_setup.py`
> re-auth the katha workflows use; the cron-job.org jobs in section 7 that triggered facts.yml can go.

# ajabgajab — launch setup checklist

Status: render engine is **built + verified** locally (103 one-fact Hinglish reels,
~31s each, sync OK, beep countdown, hi-IN Madhur/Swara rotation). What remains is
**new accounts + secrets (you)** and final wiring (config/workflow/git — next session).

Keep everything SEPARATE from the other 3 channels (no shared accounts/keys/tokens).

## 1. New Google account (→ 2FA)
- Create a fresh Gmail. Turn on 2-Step Verification (required before API/YouTube use).

## 2. New YouTube channel
- On that Google account, create the channel (name TBD — "Ajab Gajab Facts" / your pick).
- Note the **channel ID** (Settings → Advanced, `UC...`).

## 3. New GitHub account + empty repo
- New GitHub account (or a new repo under an existing one you keep separate).
- Create an empty repo named e.g. `ajabgajab` (private is fine).
- Make a **Personal Access Token (classic)** with `repo` + `workflow` scopes → save it
  (used to push + let Actions commit the ledger). This is the `github_pat.txt` value.

## 4. API keys (on the NEW Google account)
- **Gemini API key** — Google AI Studio, signed into the new account. (The 103 seed facts
  were generated with Quizora's key; the live channel MUST use its own new key.)
- **Pexels API key** — pexels.com/api (free). Reused-key is fine but a new one is cleaner.

## 5. YouTube OAuth (uploads)
- Google Cloud Console on the new account → enable **YouTube Data API v3** → create an
  **OAuth client (Desktop)** → download `client_secret.json`.
- Run `python auth_setup.py` locally (it opens a browser, you approve) → produces the
  OAuth token / `CHANNEL_CONFIG` JSON. This is the same flow the other channels used.

## 6. GitHub Actions secrets (repo → Settings → Secrets → Actions)
Paste these (values raw):
- `CHANNEL_CONFIG` — the **entire** config JSON from step 5 (credentials nested inside;
  the pipeline does `json.loads(os.environ["CHANNEL_CONFIG"])`).
- `GEMINI_API_KEY` — from step 4.
- `PEXELS_API_KEY` — from step 4.
- (Ledger commits use the Actions-provided `GITHUB_TOKEN`; the PAT from step 3 is for
  your local pushes.)

## 7. cron-job.org triggers (primary scheduler)
- Create jobs that POST to the workflow_dispatch API (same as the other 3 channels), at
  the ≤4/day slots we'll set in the new workflow. GitHub schedule crons are the backup.

## What I do next session (no accounts needed from me)
1. Add the config template + confirm `auth_setup.py` matches the new channel.
2. Add `.github/workflows/` (copy quizora's `quiz.yml`, set the ≤4/day schedule + force_post input).
3. `git init` + first commit; you add the remote (with your PAT) and push.
4. Optional polish: batch per-fact Hinglish titles, wire `image_query` into the Pexels
   fetch, Hinglish description/tags.

Once 1–7 are ready, the channel can do its first live run and we verify the same way we
did Quizora/ChartShock.

---

# Branding assets (paste image prompts into Midjourney / DALL·E / Ideogram)

Faceless, icon-driven, mobile-first. Palette: electric-yellow/orange glow on deep
indigo→violet (swap to teal/white on navy if you want it to match the video look).

## Profile picture (avatar) — image prompt
Flat vector logo icon for a YouTube channel called "Ajab Gajab Facts", an Indian
amazing-facts channel. A bold glowing lightbulb fused with a human brain, a small
spark/exclamation burst around it, and a subtle question-mark motif. Vibrant
electric-yellow and orange glow on a deep indigo-to-violet gradient background. Thick
clean outlines, high contrast, centered, simple enough to read as a tiny circular icon.
Playful, energetic, "mind-blown" feeling. No text, no face, no photorealism. 1:1 square,
800x800, crisp edges, solid background.

## Banner (channel art) — image prompt
YouTube channel banner for "Ajab Gajab Facts", an Indian Hinglish amazing-facts channel.
Wide horizontal composition, 2560x1440. Deep indigo-to-violet night-sky gradient with soft
glowing bokeh sparks. Centered: the bold playful title "AJAB GAJAB FACTS" in a chunky
rounded sans-serif, electric-yellow/orange with a subtle glow, and a small tagline under it
"Rozana Ajab Gajab Facts | Daily Amazing Facts". Flanked by minimal glowing icons -
lightbulb, brain, question mark, India map silhouette, cricket ball, film reel - spread wide
but keep ALL text and key icons inside the centered 1546x423 safe area (the rest is just
background glow that gets cropped on mobile). Clean, high-contrast, mobile-first, no photos
of real people, no watermark.
**Keep name/tagline within the center 1546x423 safe area — that's all phones show.**

# Channel description

**Short tagline (first line):**
Rozana ke Ajab Gajab Facts jo aapko hairaan kar denge | Daily amazing facts in Hinglish.

**Full "About":**
Ajab Gajab Facts mein aapka swagat hai!

Yahan milte hain India aur duniya ke sabse ajab-gajab, mind-blowing facts - science,
history, cricket, movies, GK aur bahut kuch. Har fact ek chhota sa quiz hai: guess kijiye,
phir sahi jawab jaaniye!

- Rozana naye facts (Daily amazing facts)
- Hinglish mein - simple aur mazedaar
- Har video sirf 30 seconds

Kitne facts aapko pehle se pata the? Comment mein batayein aur Subscribe zaroor karein
taaki koi ajab-gajab fact miss na ho!

#AjabGajabFacts #AmazingFacts #Facts #Hindi #India #DidYouKnow #GK

**Channel keywords (settings -> keywords):**
ajab gajab facts, amazing facts, facts in hindi, hinglish facts, did you know, gk facts,
india facts, interesting facts, daily facts, mind blowing facts, cricket facts, bollywood facts
