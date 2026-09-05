"""
Quality Scorer — zero AI tokens, pure rule-based analysis.
Scores generated scripts/videos 0-10 before upload decision.
DORMANT self-updating path: _load_channel_learnings() reads
analytics_report.json to reinforce title patterns that are actually working
(1-hour cache, no AI tokens). **Nothing in this repo writes that file** — there
is no analytics workflow here, it was the Money Sorted workflow's data bus — so
the function has always returned {} and the scorer has never once self-updated.
Verified 2026-09-06 by calling it. Kept rather than deleted (Quizora deleted its
copy on 2026-08-02) because it is latent, not broken: add an analytics workflow
that writes the report and it starts working. Until then, do not reason about
this scorer as if it adapts.
"""
import os, re, json, time
from dataclasses import dataclass, field
from pathlib import Path

# ChartShock: no jurisdiction-specific figure rules — figure accuracy is
# enforced by the chart-sync rule (Gemini may only cite numbers from charts.py,
# which carries a source per topic). Keep the list for future known-bad claims.
OUTDATED_FIGURES = [
    (r'pluto\s+is\s+(?:a\s+)?planet\b', "Pluto is a dwarf planet — phrase carefully"),
]
RISKY_PHRASES = ["guaranteed", "you will earn", "risk-free", "secret loophole", "get rich", "miracle"]
# "Authority terms" here = credibility markers for a data channel: sources +
# comparison vocabulary the narration should lean on.
AU_TERMS      = ["question", "answer", "correct", "score", "comment", "guess",
                 "riddle", "quiz", "think fast", "three", "round", "count"]

# Openers that kill retention in first 0.5s — viewers scroll before hook lands
_BANNED_OPENERS = [
    "today we", "in this video", "in today's", "hi everyone", "hey everyone",
    "welcome to", "what's up", "let me explain", "so today", "in this short",
    "alright so", "okay so", "hello everyone",
]

# ── Channel authority config (loaded from channel.yaml per CHANNEL_NAME) ──────
_channel_authority_cache: dict = {"data": None, "ts": 0.0}

def _load_channel_authority() -> dict:
    """
    Load authority_terms and disclaimer phrases from channels/<name>/channel.yaml.
    Falls back to AU super defaults when CHANNEL_NAME is not set.
    Cached 1h — zero I/O on hot path.
    """
    now = time.time()
    if _channel_authority_cache["data"] is not None and now - _channel_authority_cache["ts"] < 3600:
        return _channel_authority_cache["data"]

    defaults = {
        "authority_terms":  AU_TERMS,
        "disclaimer_text":  "not financial advice",
        "disclaimer_alt":   "licensed financial adviser",
    }
    channel_name = os.environ.get("CHANNEL_NAME", "")
    if not channel_name:
        _channel_authority_cache.update({"data": defaults, "ts": now})
        return defaults

    for candidate in [
        Path.cwd() / "channels" / channel_name / "channel.yaml",
        Path(__file__).parent / "channels" / channel_name / "channel.yaml",
    ]:
        if not candidate.exists():
            continue
        try:
            try:
                import yaml
                cfg = yaml.safe_load(candidate.read_text(encoding="utf-8"))
            except ImportError:
                json_p = candidate.with_suffix(".json")
                if not json_p.exists():
                    continue
                cfg = json.loads(json_p.read_text(encoding="utf-8"))
            auth_terms = cfg.get("authority_terms", AU_TERMS)
            disclaimer = cfg.get("disclaimer", "")
            words = disclaimer.lower().split()
            # "general information" is universal; secondary = first 3 words of disclaimer
            dis_text = "general information"
            dis_alt  = " ".join(words[:3]) if len(words) >= 3 else dis_text
            result = {
                "authority_terms": auth_terms,
                "disclaimer_text": dis_text,
                "disclaimer_alt":  dis_alt,
            }
            _channel_authority_cache.update({"data": result, "ts": now})
            return result
        except Exception:
            pass

    _channel_authority_cache.update({"data": defaults, "ts": now})
    return defaults


# ── Channel learnings (self-updating from analytics_report.json) ──────────────
_learnings_cache: dict = {"data": None, "ts": 0.0}

def _load_channel_learnings() -> dict:
    """
    Parse analytics_report.json to derive what title patterns are actually
    working on this channel. Zero AI tokens. Cached 1h to avoid I/O per video.
    Returns {} if the report is missing or has <5 videos (insufficient data).
    """
    now = time.time()
    if _learnings_cache["data"] is not None and now - _learnings_cache["ts"] < 3600:
        return _learnings_cache["data"]

    for candidate in [
        Path.cwd() / "analytics_report.json",
        Path(__file__).parent / "analytics_report.json",
    ]:
        if not candidate.exists():
            continue
        try:
            report  = json.loads(candidate.read_text(encoding="utf-8"))
            videos  = [v for v in report.get("my_videos", []) if v.get("views", 0) > 0]
            if len(videos) < 5:
                break

            avg_views = sum(v["views"] for v in videos) / len(videos)
            high = [v for v in videos if v["views"] >= avg_views]
            low  = [v for v in videos if v["views"] <  avg_views]

            def _rate(lst, fn):
                return sum(1 for v in lst if fn(v.get("title", ""))) / len(lst) if lst else 0.0

            q_rate_high   = _rate(high, lambda t: "?" in t)
            q_rate_low    = _rate(low,  lambda t: "?" in t)
            fig_rate_high = _rate(high, lambda t: bool(re.search(r'\$[\d,]+[kKmM]?|\d+%', t[:35])))
            fig_rate_low  = _rate(low,  lambda t: bool(re.search(r'\$[\d,]+[kKmM]?|\d+%', t[:35])))
            vs_rate_high  = _rate(high, lambda t: " vs " in t.lower())

            # Duration data if available
            dur_data   = [v["duration_seconds"] for v in videos if "duration_seconds" in v]
            high_dur   = [v["duration_seconds"] for v in high   if "duration_seconds" in v]
            opt_length = (round(sum(high_dur)/len(high_dur), 0) if high_dur else 38.0)

            learnings = {
                "sample_size":       len(videos),
                "avg_views":         round(avg_views, 1),
                "question_uplift":   round(q_rate_high   - q_rate_low,    2),
                "figure_uplift":     round(fig_rate_high - fig_rate_low,  2),
                "vs_rate_high":      round(vs_rate_high,  2),
                "q_rate_high":       round(q_rate_high,   2),
                "optimal_length_s":  opt_length,
            }
            _learnings_cache["data"] = learnings
            _learnings_cache["ts"]   = now
            return learnings
        except Exception:
            pass

    return {}


# Viral hook structural features — each worth 1-2 points toward a 0-10 viral score
_LOSS_WORDS    = ["costing", "losing", "miss", "less than", "drop", "short", "wasting", "stealing", "falling behind"]
_URGENCY_WORDS = ["now", "before", "deadline", "today", "soon", "while", "by the time"]
_QUESTION_OPENERS = ["is your", "are you", "did you know", "can you", "what if", "why is", "how much", "have you"]


@dataclass
class QualityReport:
    factual_accuracy: float = 0.0
    content_quality:  float = 0.0
    au_specificity:   float = 0.0
    safety_score:     float = 0.0
    title_quality:    float = 0.0
    total:            float = 0.0
    viral_hook_score: float = 0.0   # 0-10 structural hook analysis (not in gate total)
    weakest_dimension: str = ""     # which dimension has most room to improve
    media_qa: dict = field(default_factory=dict)  # duration/RMS/contrast checks
    issues:    list = field(default_factory=list)
    positives: list = field(default_factory=list)

    def summary(self) -> str:
        if self.total >= 8:   return "Excellent [PASS]"
        if self.total >= 7:   return "Good [PASS]"
        if self.total >= 6.5: return "Acceptable [PASS]"
        return "Poor [FAIL]"


def score_viral_hook(hook: str) -> tuple[float, list[str]]:
    """
    Structural hook analysis for QUIZ Shorts.
    Returns (score_0_to_10, list_of_matched_features).
    Does NOT affect the gate score — informational only.

    This used to grade against AU *finance* patterns — points for dollar figures,
    loss framing, "your super", AU finance authority terms. Inherited from the
    other channel, and it scored every quiz hook near zero for the crime of not
    mentioning money, which made the number worse than useless: it was actively
    misleading. A quiz hook lives or dies on the curiosity gap instead.

    Now the intro narration IS the hook and nothing else (no title card, no
    "count your score" preamble), so this is literally the first thing a viewer
    hears, and it is the only thing standing between them and question 1.
    """
    if not hook:
        return 0.0, ["no hook"]
    h = hook.lower().strip()
    words = h.split()
    hits = []
    pts = 0.0

    # A challenge the viewer wants to disprove — "only 1 in 10 get all three",
    # "99% get this wrong". The single strongest quiz-hook pattern: it dares you.
    if re.search(r"\b(only|nobody|no one|almost no one|hardly anyone)\b", h) or \
       re.search(r"\b\d+\s*%|\b\d+\s+in\s+\d+\b", h):
        pts += 3.0; hits.append("challenge / difficulty claim")

    # Names the failure explicitly: fool, miss, fail, trip up, get wrong
    if re.search(r"\b(fool|fools|wrong|miss(es)?|fail|stump|trick|beat)\w*\b", h):
        pts += 2.0; hits.append("failure framing (bait to prove otherwise)")

    # Second person — the viewer is the one being tested, not "people"
    if re.search(r"\b(you|your|you're|yourself)\b", h):
        pts += 2.0; hits.append("you-address")

    # A concrete number anywhere (three questions, 1 in 10, 99%)
    if re.search(r"\b(\d+|one|two|three)\b", h):
        pts += 1.0; hits.append("specific number")

    # Question format
    if "?" in hook or any(h.startswith(op) for op in _QUESTION_OPENERS):
        pts += 1.0; hits.append("question format")

    # Superlative / extreme — most, deadliest, never, biggest
    if re.search(r"\b(most|least|best|worst|never|always|biggest|deadliest|richest|oldest)\b", h):
        pts += 1.0; hits.append("superlative")

    # Spoken length: this is heard, not read. Over ~18 words and the viewer has
    # swiped before the hook lands.
    if 5 <= len(words) <= 16:
        pts += 1.0; hits.append(f"{len(words)}-word hook")
    else:
        hits.append(f"word count {len(words)} (target 5-16 — it is SPOKEN first)")

    pts = min(10.0, pts)

    # Load viral_patterns.json for pattern match bonus
    patterns_file = Path(__file__).parent / "viral_patterns.json"
    if patterns_file.exists():
        try:
            patterns = json.loads(patterns_file.read_text(encoding="utf-8"))
            matched = [p["label"] for p in patterns
                       if any(kw.lower() in h for kw in p.get("keywords", []))]
            if matched:
                pts = min(10.0, pts + 0.5)
                hits.append(f"matches pattern: {matched[0]}")
        except Exception:
            pass

    return min(10.0, round(pts, 1)), hits


def score_media_artifacts(json_path: Path) -> dict:
    """
    Read the matching .mp4 and .png from the same directory as json_path.
    Checks: video duration (Shorts 32-45s sweet spot), audio RMS (dBFS), thumbnail contrast.
    Returns findings dict — never raises, returns {} on any failure.
    Heavy imports (moviepy, PIL, numpy) are lazy so this doesn't slow the fast path.
    """
    result = {}
    mp4 = json_path.with_suffix(".mp4")
    png = json_path.with_suffix(".png")

    if mp4.exists():
        try:
            from moviepy.editor import VideoFileClip
            import numpy as np
            with VideoFileClip(str(mp4)) as clip:
                dur = clip.duration
                result["duration_s"] = round(dur, 1)
                # 1-fact Hinglish reels run ~25-40s by design (the 32-45s band was
                # tuned for 3-question quizzes and warned on EVERY reel — a check
                # that always fires trains you to ignore the QA output).
                if 22 <= dur <= 42:
                    result["duration_ok"] = True
                    result["duration_note"] = f"{dur:.1f}s — sweet spot"
                elif dur < 22:
                    result["duration_ok"] = False
                    result["duration_note"] = f"{dur:.1f}s — too short (1-fact reel target 22-42s)"
                else:
                    result["duration_ok"] = False
                    result["duration_note"] = f"{dur:.1f}s — too long (may not loop well)"

                if clip.audio:
                    try:
                        import math, subprocess
                        # Extract raw PCM via ffmpeg — avoids moviepy.to_soundarray
                        # which broke on recent numpy ("arrays to stack must be a sequence").
                        pcm = subprocess.run(
                            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(mp4),
                             "-vn", "-ac", "1", "-ar", "22050", "-f", "s16le", "-"],
                            capture_output=True, timeout=30,
                        )
                        if pcm.returncode != 0 or not pcm.stdout:
                            raise RuntimeError(
                                f"ffmpeg pcm extract failed: {pcm.stderr[:80].decode(errors='replace')}"
                            )
                        samples = np.frombuffer(pcm.stdout, dtype=np.int16).astype(np.float32) / 32768.0
                        rms = float(np.sqrt(np.mean(samples ** 2)))
                        db = 20 * math.log10(rms + 1e-9)
                        result["audio_rms_db"] = round(db, 1)
                        if -20 <= db <= -10:
                            result["audio_ok"] = True
                            result["audio_note"] = f"{db:.1f} dBFS — levels ok"
                        elif db < -20:
                            result["audio_ok"] = False
                            result["audio_note"] = f"{db:.1f} dBFS — too quiet"
                        else:
                            result["audio_ok"] = False
                            result["audio_note"] = f"{db:.1f} dBFS — check for clipping"
                    except Exception as ae:
                        result["audio_ok"] = None
                        result["audio_note"] = f"RMS check skipped: {str(ae)[:60]}"

            # Silence detection — mid-video dead air >0.6s kills Shorts retention.
            # Excludes first/last 0.5s of the clip (intro/outro fades are normal).
            try:
                import subprocess
                proc = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4),
                     "-af", "silencedetect=noise=-30dB:d=0.6", "-f", "null", "-"],
                    capture_output=True, text=True, timeout=30,
                )
                gaps = []
                pending_start = None
                for line in proc.stderr.splitlines():
                    if "silence_start:" in line:
                        try:
                            pending_start = float(line.split("silence_start:")[1].strip().split()[0])
                        except (ValueError, IndexError):
                            pending_start = None
                    elif "silence_duration:" in line and pending_start is not None:
                        try:
                            sdur = float(line.split("silence_duration:")[1].strip().split()[0])
                            if pending_start >= 0.5 and (pending_start + sdur) <= (dur - 0.5):
                                gaps.append((round(pending_start, 2), round(sdur, 2)))
                        except (ValueError, IndexError):
                            pass
                        pending_start = None
                if gaps:
                    worst = max(gaps, key=lambda x: x[1])
                    result["silence_ok"] = False
                    result["silence_note"] = (
                        f"{len(gaps)} mid-video gap(s) >0.6s; worst {worst[1]}s @ {worst[0]}s"
                    )
                else:
                    result["silence_ok"] = True
                    result["silence_note"] = "no mid-video dead-air gaps"
            except subprocess.TimeoutExpired:
                result["silence_ok"] = None
                result["silence_note"] = "silencedetect timed out"
            except Exception as se:
                result["silence_ok"] = None
                result["silence_note"] = f"silencedetect skipped: {str(se)[:60]}"
        except Exception as e:
            result["media_error"] = str(e)[:120]

    if png.exists():
        try:
            from PIL import Image
            import numpy as np
            arr = np.array(Image.open(png).convert("L"))
            contrast = float(arr.std())
            result["thumb_contrast"] = round(contrast, 1)
            if contrast >= 55:
                result["thumb_ok"] = True
                result["thumb_note"] = f"contrast={contrast:.0f} — strong"
            elif contrast >= 35:
                result["thumb_ok"] = True
                result["thumb_note"] = f"contrast={contrast:.0f} — acceptable"
            else:
                result["thumb_ok"] = False
                result["thumb_note"] = f"contrast={contrast:.0f} — low (thumbnail may not pop)"
        except Exception as e:
            result["thumb_error"] = str(e)[:120]

    return result


def score_pipeline_output(script: dict, pipeline_type: str, log_output: str = "") -> QualityReport:
    r = QualityReport()
    title = script.get("title",""); hook = script.get("hook","")
    rising = script.get("rising",""); conflict = script.get("conflict","")
    comeback = script.get("comeback",""); payoff = script.get("payoff","")
    narration = script.get("narration",""); description = script.get("description","")
    tags_str  = " ".join(script.get("tags", []))
    topic_str = script.get("topic", "")
    # Animated pipeline has no hook field — derive from first narration sentence
    if pipeline_type == "animated" and not hook and narration:
        hook = re.split(r'[.!?]', narration)[0].strip()
    full = " ".join([title,hook,rising,conflict,comeback,payoff,narration,description,tags_str,topic_str]).lower()

    # Factual (3.0)
    sf = 3.0
    for pattern, msg in OUTDATED_FIGURES:
        if re.search(pattern, full, re.I):
            sf -= 1.5; r.issues.append(f"Outdated figure: {msg}")
    r.factual_accuracy = max(0, sf)

    # Content (2.5)
    sc = 2.5
    if not hook: sc -= 1.0; r.issues.append("No hook")
    else:
        if "?" not in hook and not any(f in hook.lower() for f in ["did you know","can you","if you"]): sc -= 0.3
        # For animated: narration uses spoken numbers — also accept dollar figure in title
        hook_has_figure = bool(re.search(r'\$[\d,]+|\d+%', hook))
        title_has_figure = bool(re.search(r'\$[\d,]+[kKmM]?|\d+%', title))
        if hook_has_figure or (pipeline_type == "animated" and title_has_figure):
            r.positives.append("Hook has specific figure")
        else:
            sc -= 0.2
    words = sum(len(b.split()) for b in [hook,rising,conflict,comeback,payoff,narration] if b)
    _wmin, _wmax = (80, 120) if pipeline_type != "animated" else (75, 110)
    if words < _wmin: sc -= 0.5; r.issues.append(f"Too short: {words} words (min {_wmin})")
    elif words > _wmax: sc -= 0.3; r.issues.append(f"Too long: {words} words (max {_wmax})")
    else: r.positives.append(f"Good length: {words} words")
    if "*" in full: sc -= 0.3; r.issues.append("Asterisk found — TTS will speak it")

    # Hook-title format consistency — listicle hook needs listicle title
    _listicle_re = re.compile(r'\b(?:three|four|five|six|\d+)\b.{0,40}(?:ways?|moves?|tips?|steps?|things?|mistakes?|reasons?)', re.I)
    if _listicle_re.search(hook) and not _listicle_re.search(title):
        sc -= 0.5; r.issues.append("Listicle hook but title is not listicle format — viewer mismatch")

    # Banned openers — death in Shorts (viewer bounces before hook lands)
    script_start = (hook + " " + rising).lower()[:120]
    opener_hit = next((o for o in _BANNED_OPENERS if script_start.startswith(o)), None)
    if opener_hit:
        sc -= 0.4; r.issues.append(f"Banned opener '{opener_hit}' — kills retention <0.5s")

    # Specific figure count — 2-4 is optimal for AU finance Shorts.
    # Animated narration uses spoken-out numbers ("thirty thousand", "two million")
    # because TTS reads symbols badly — also count those, plus accept any figure in
    # the title (which is always written numerically and is what viewers see).
    script_body = " ".join(b for b in [hook, rising, conflict, comeback, payoff, narration] if b)
    fig_count = len(re.findall(r'\$[\d,]+[kKmM]?|\d+(?:\.\d+)?%|\d{1,3}(?:,\d{3})+', script_body))
    spoken_count = len(re.findall(
        r'\b(?:thousand|million|billion|percent|per cent)\b', script_body, re.I))
    title_has_fig = bool(re.search(r'\$[\d,]+[kKmM]?|\d+%', title))
    effective_figs = fig_count + spoken_count + (1 if title_has_fig and fig_count == 0 else 0)
    if effective_figs == 0:
        sc -= 0.25; r.issues.append("No specific figures — vague content underperforms")
    elif 2 <= effective_figs <= 4:
        r.positives.append(f"{effective_figs} specific figures (optimal range)")
    elif effective_figs >= 6:
        sc -= 0.15; r.issues.append(f"{effective_figs} figures may overwhelm viewer")

    # Arc completeness (text pipeline only)
    if pipeline_type != "animated":
        for section in ["rising", "conflict", "comeback", "payoff"]:
            if not script.get(section, "").strip():
                sc -= 0.3; r.issues.append(f"Missing '{section}' — incomplete conflict arc")

    # Sentence length for TTS pacing — >22 words per sentence = robotic delivery
    sentences = [s.strip() for s in re.split(r'[.!?]+', script_body) if s.strip()]
    long_sents = [s for s in sentences if len(s.split()) > 22]
    if len(long_sents) >= 2:
        sc -= 0.2; r.issues.append(f"{len(long_sents)} sentences >22 words — TTS pacing suffers")

    # First 7 words of hook must have tension or a figure
    first7 = " ".join(hook.split()[:7]).lower()
    has_tension = any(w in first7 for w in ["your", "you", "costing", "losing", "missing",
                                             "hidden", "wrong", "mistake", "secret", "most"])
    # Facts channel: any bare number ("17.1 million", "1.3 seconds") is a figure
    has_fig_early = bool(re.search(r'\d', " ".join(hook.split()[:7])))
    if not has_tension and not has_fig_early:
        sc -= 0.15; r.issues.append("First 7 hook words lack tension or figure — weak retention")
    else:
        r.positives.append("Strong hook opening")

    # CTA in description
    if any(w in description.lower() for w in ["subscribe", "follow", "like", "comment"]):
        r.positives.append("CTA in description")

    r.content_quality = max(0, sc)

    # Niche specificity (1.5) — channel-aware: uses authority_terms from channel.yaml
    authority = _load_channel_authority()
    niche_terms = authority["authority_terms"]
    sa = 1.5
    niche_count = sum(1 for t in niche_terms if t in full)
    if niche_count < 2: sa -= 1.0; r.issues.append(f"Only {niche_count} niche authority terms — fails specificity")
    elif niche_count < 4: sa -= 0.3
    else: r.positives.append(f"{niche_count} niche authority terms")
    r.au_specificity = max(0, sa)

    # Safety (1.5)
    ss = 1.5
    for phrase in RISKY_PHRASES:
        if phrase in full: ss -= 0.5; r.issues.append(f"Risky phrase: '{phrase}'")
    dis_text = authority["disclaimer_text"]
    dis_alt  = authority["disclaimer_alt"]
    if dis_text in full or dis_alt in full:
        r.positives.append("Disclaimer present")
    else:
        ss -= 0.3; r.issues.append("Missing disclaimer")
    r.safety_score = max(0, ss)

    # Title (1.5)
    learnings = _load_channel_learnings()
    st = 1.5
    if not title: st -= 1.5; r.issues.append("No title")
    else:
        tl = len(title)
        if tl < 20: st -= 0.5; r.issues.append(f"Title too short: {tl}")
        elif tl > 60: st -= 0.3; r.issues.append(f"Title too long: {tl}")
        has_fig = bool(re.search(r'\$[\d,]+[kKmM]?|\d+(?:[.,]\d+)?', title[:35]))
        has_q   = "?" in title
        has_vs  = " vs " in title.lower() or "than" in title.lower()
        if has_fig:
            r.positives.append("Figure in first 35 chars")
        else:
            st -= 0.2; r.issues.append("No figure in first 35 chars")
        # Hard-coded baseline: question + figure = top-CTR pattern (16-video data)
        if has_fig and (has_q or has_vs):
            st = min(1.5, st + 0.2)
            r.positives.append("Title: question+figure combo (proven top-CTR pattern)")
        elif not has_q and not has_vs:
            st -= 0.1; r.issues.append("Title: no question or comparison (lower CTR pattern)")
        # Curiosity-killer prefixes — 33-video data shows "Budget 2026:" / "Federal Budget"
        # prefixed titles average 17 views vs 37 for everything else post-launch.
        # Generic news framing replaces the curiosity gap with a label.
        if re.match(r'^\s*(?:budget\s*20\d{2}|federal\s*budget)\s*:', title, re.I):
            st -= 0.35
            r.issues.append("Title prefix 'Budget 20XX:' kills curiosity (2x view drop in our data)")
        # Self-updating bonus: reinforce patterns observed in THIS channel's top performers
        n = learnings.get("sample_size", 0)
        if n >= 8:
            q_up  = learnings.get("question_uplift", 0.0)
            f_up  = learnings.get("figure_uplift",   0.0)
            extra = 0.0
            notes = []
            if has_q and q_up >= 0.20:
                bump = min(0.12, q_up * 0.3)
                extra += bump; notes.append(f"?-title uplift +{q_up:.0%} in our {n} videos")
            if has_fig and f_up >= 0.15:
                bump = min(0.08, f_up * 0.25)
                extra += bump; notes.append(f"$-title uplift +{f_up:.0%} in our {n} videos")
            if extra > 0:
                st = min(1.5, st + extra)
                r.positives.append("Title learnings: " + " | ".join(notes))
    r.title_quality = max(0, st)

    r.total = round(r.factual_accuracy + r.content_quality + r.au_specificity + r.safety_score + r.title_quality, 2)
    # Hard-fail: any outdated figure caps total below the 6.5 gate regardless of other scores
    if r.factual_accuracy < 3.0:
        r.total = min(r.total, 5.9)
        r.issues.append("HARD FAIL: factual error forces score below upload gate")

    # Weakest dimension — highest gap from max (guides targeted retry hint)
    gaps = {
        "factual":  3.0 - r.factual_accuracy,
        "content":  2.5 - r.content_quality,
        "au":       1.5 - r.au_specificity,
        "safety":   1.5 - r.safety_score,
        "title":    1.5 - r.title_quality,
    }
    r.weakest_dimension = max(gaps, key=gaps.get)

    # Viral hook score (informational, not in gate)
    r.viral_hook_score, viral_hits = score_viral_hook(hook)

    # Log learnings summary if data available
    if learnings.get("sample_size", 0) >= 5:
        r.positives.append(
            f"[Learnings] {learnings['sample_size']} videos, "
            f"avg {learnings['avg_views']:.0f} views, "
            f"?-uplift={learnings.get('question_uplift',0):+.0%}, "
            f"$-uplift={learnings.get('figure_uplift',0):+.0%}"
        )

    return r


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2: print("Usage: python quality_scorer.py <script.json> [text|animated]"); sys.exit(1)
    ptype = sys.argv[2] if len(sys.argv) > 2 else "text"
    json_path = Path(sys.argv[1])
    with open(json_path) as f: script = json.load(f)
    rpt = score_pipeline_output(script, ptype)
    print(f"\nScore: {rpt.total:.1f}/10 — {rpt.summary()}")
    print(f"  Factual: {rpt.factual_accuracy:.1f}/3.0  Content: {rpt.content_quality:.1f}/2.5  "
          f"AU: {rpt.au_specificity:.1f}/1.5  Safety: {rpt.safety_score:.1f}/1.5  Title: {rpt.title_quality:.1f}/1.5")
    print(f"  Viral hook: {rpt.viral_hook_score:.0f}/10  Weakest: {rpt.weakest_dimension}")
    for i in rpt.issues:    print(f"  FAIL {i}")
    for p in rpt.positives: print(f"  PASS {p}")

    # Media artifact checks (only when .mp4/.png exist alongside the JSON)
    media = score_media_artifacts(json_path)
    if media:
        print("\n  -- Media QA --")
        for k, v in media.items():
            if k.endswith("_error"):
                print(f"  WARN {v}")
            elif k.endswith("_note"):
                ok_flag = media.get(k[:-5] + "_ok")  # e.g. duration_note → duration_ok
                prefix = "  ok  " if ok_flag else ("  WARN" if ok_flag is False else "  info")
                print(f"  {prefix} {v}")
