"""Affiliate/referral block builder for video descriptions.

Reads affiliates.json (tracked in the repo so GitHub Actions checkouts see it —
same data-bus pattern as topic_ledger.json). Offers stay dormant until a real
URL is pasted in and "active" is flipped to true; nothing else needs touching.
Both pipelines call build_affiliate_block() and get "" when no offer is live,
so descriptions are unchanged until then.

Standalone by design (stdlib only) — importable from pipeline.py,
pipeline_animated.py, and tests without pulling in heavy dependencies.
"""
import json
from pathlib import Path

_CONFIG = Path(__file__).parent / "affiliates.json"


def _load_offers() -> dict:
    try:
        return json.loads(_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _live_offers(cfg: dict, concept: str) -> list:
    """Active offers with a real URL that target this concept (or '*'),
    concept-specific offers first."""
    live = []
    for o in cfg.get("offers", []):
        if not o.get("active"):
            continue
        url = str(o.get("url", ""))
        if not url.lower().startswith("http"):
            continue  # placeholder or malformed — never publish it
        targets = o.get("concepts", ["*"])
        if "*" in targets or (concept and concept in targets):
            live.append(o)
    live.sort(key=lambda o: "*" in o.get("concepts", ["*"]))
    return live


def spoken_cta(concept: str = "") -> str:
    """One short spoken line for the narration CTA beat, from the first live
    offer that defines 'spoken_cta'. "" when nothing applies. Never raises."""
    try:
        cfg = _load_offers()
        for o in _live_offers(cfg, concept):
            line = str(o.get("spoken_cta", "")).strip()
            if line:
                return line
        return ""
    except Exception:
        return ""


def comment_text(concept: str = "") -> str:
    """Dedicated affiliate comment. YouTube renders links in Shorts comments
    as plain text (Aug 2023 anti-spam policy) AND the mobile app has no
    text-selection in comments, so mobile viewers can neither tap nor copy a
    URL here. The mobile route is the channel profile link (tap the channel
    name -> the link sits on the profile) — the raw URLs stay in the comment
    for desktop viewers, where they render clickable. Disclosures stay in the
    same comment as the links (required adjacency). "" when no offer is live.
    Never raises."""
    try:
        cfg = _load_offers()
        cap = int(cfg.get("max_offers_per_video", 2))
        live = _live_offers(cfg, concept)[:cap]
        if not live:
            return ""
        lines, extra = [], []
        for o in live:
            lines.append(f"{o.get('label', 'Link')}:")
            lines.append(o["url"])
            lines.append("")
            d = str(o.get("disclosure", "")).strip()
            if d and d not in extra:
                extra.append(d)
        lines.append("On your phone? Links in Shorts comments aren't tappable — "
                     "tap our channel name instead and the link is right on our profile.")
        disclosure = str(cfg.get(
            "disclosure",
            "Some links above are referral links — the channel may earn a "
            "commission at no extra cost to you.",
        ))
        lines.append(" ".join([disclosure] + extra))
        return "\n".join(lines)
    except Exception:
        return ""


def build_affiliate_block(concept: str = "") -> str:
    """Description block for the given video concept, or "" when no active
    offer applies. Never raises — a broken config must not block an upload."""
    try:
        cfg = _load_offers()
        cap = int(cfg.get("max_offers_per_video", 2))
        live = _live_offers(cfg, concept)
        if not live:
            return ""
        lines = [str(cfg.get("heading", "Helpful tools (channel partners):"))]
        extra_disclosures = []
        for o in live[:cap]:
            lines.append(f"▸ {o.get('label', 'Link')}: {o['url']}")
            # Program-mandated wording (e.g. Amazon Associates) rides with its offer.
            d = str(o.get("disclosure", "")).strip()
            if d and d not in extra_disclosures:
                extra_disclosures.append(d)
        disclosure = str(cfg.get(
            "disclosure",
            "Some links above are referral links — the channel may earn a "
            "commission at no extra cost to you.",
        ))
        lines.append(" ".join([disclosure] + extra_disclosures))
        return "\n".join(lines)
    except Exception:
        return ""
