"""
Heartbeat check: a daily competitive-intelligence brief for the user's business
(Starrdam Intelligence). Fires once per day at the configured trigger_hour.

Grounded in the business + competitor memories the user has taught Trillion — it
does NOT hit the live web (heartbeat runs locally and must never block or raise
on a network call). Each day it rotates the analytical angle so the brief stays
fresh instead of repeating, and asks the model for one sharp insight plus one
concrete execution action.

To make it live-news-driven later, a fetch step could be added here behind a
timeout — but keep the never-raises contract: a research outage must degrade to
"no brief today", never crash the heartbeat.
"""
from __future__ import annotations

from datetime import date

# Rotating daily lens so a week of briefs covers different ground.
_ANGLES = [
    "a competitor move to watch (Tantita, Halogen, G4S, GardaWorld) and how Starrdam should respond",
    "one under-served sector (government, aviation, energy, maritime, rail, corporate) to push this week and why",
    "a sharpening of Starrdam's positioning against a named rival",
    "one business-development action to win a specific type of contract",
    "an operational or capability gap to close before a competitor exploits it",
    "a Nigerian regulatory or market shift (CAC/NSCDC/NCAA/NPF) worth acting on",
    "a differentiation play that does not require matching a rival on scale or drones",
    "a defence-acquisition move: DICON alignment, an OEM to partner (Proforce/Terra/BabaSky), or a sustainment/MRO angle",
    "a corporate-security growth play: managed monitoring/analytics, a physical+cyber bundle, or an NDPA-compliance wedge",
    "a LinkedIn or tender-channel move for the defence-acquisition (B2G) line",
]


def _business_context() -> str:
    """Concatenate the taught business + competitor memories as grounding.
    Returns '' if the store is empty or unreachable — the caller then skips."""
    try:
        from trillion.memory_store import FileMemoryStore
        from trillion.memory_recall import recall
        store = FileMemoryStore()
        res = recall("Starrdam business competitors strategy positioning sectors", store, k=8)
        lines = [f"- {m.hook}: {m.body}" for m in res.memories if "starrdam" in (m.hook + m.body).lower()]
        return "\n".join(lines)
    except Exception:
        return ""


def run() -> list[dict] | None:
    context = _business_context()
    if not context:
        return None   # nothing taught yet — no brief to give

    angle = _ANGLES[date.today().toordinal() % len(_ANGLES)]
    system = (
        "You are a competitive-strategy advisor for Starrdam Intelligence, a "
        "Nigeria-based security & defence firm. Its two priority lines are "
        "(1) defence acquisition & maintenance (B2G — sell via LinkedIn, DICON, "
        "and tenders, not Instagram) and (2) corporate security (Instagram works "
        "for this audience + recruitment). Weight advice toward these two. Ground "
        "every claim in the business facts provided — never invent competitors, "
        "contracts, or numbers. Be concrete and blunt. No preamble."
    )
    prompt = (
        f"Business & competitor knowledge:\n{context}\n\n"
        f"Today's focus: {angle}.\n\n"
        "Give a daily brief in this exact shape, under 130 words total:\n"
        "INSIGHT: <one sharp, specific observation>\n"
        "ACTION: <one concrete thing to do today or this week>\n"
        "OPPORTUNITY: <one opportunity in defence acquisition OR corporate security>\n"
        "POST: <one OPSEC-safe social/story idea — no client sites, faces, or live ops; "
        "name the channel (Instagram for corporate/brand, LinkedIn for defence acquisition)>"
    )
    try:
        from trillion.provider import complete
        text = complete(prompt, system=system, max_tokens=340).strip()
    except Exception:
        return None
    if not text:
        return None

    return [{
        "message": f"📊 Starrdam competitive brief\n{text}",
        "priority": "low",
    }]
