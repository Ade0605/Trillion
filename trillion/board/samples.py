"""
samples — one realistic, generic example of every block, validated through the
same path the model's output takes. The style page draws these, so if a block
ever renders wrong it shows here first (fix the validator/recipe, not the model).
"""
from __future__ import annotations

from .blocks import validate_block, BLOCK_TYPES

_RAW: dict[str, dict] = {
    "value": {"block": "value", "label": "Revenue this year", "value": "$184,000",
              "change": "+12% vs last year", "changeTone": "good",
              "hint": "Through November"},
    "chart": {"block": "chart", "kind": "line",
              "series": [{"name": "2026", "points": [12, 15, 14, 19, 22, 25, 24, 28, 31, 30, 34]}],
              "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"]},
    "table": {"block": "table", "columns": ["Deal", "Stage", "Value"],
              "rows": [["Aviation Authority", "Proposal", "$48k"],
                       ["Port Security", "Negotiation", "$120k"],
                       ["Bank HQ", "Qualified", "$32k"]]},
    "rows": {"block": "rows", "items": [
        {"title": "Reply to NCAA tender query", "detail": "Due today", "meta": "2h", "tone": "attention"},
        {"title": "Sign off drone MRO quote", "detail": "Waiting on you", "meta": "1d"},
        {"title": "Call Port Harcourt site lead", "meta": "3d"}]},
    "meter": {"block": "meter", "kind": "ring", "value": 68,
              "label": "Q4 target", "caption": "68% of $250k", "tone": "good"},
    "timeline": {"block": "timeline", "items": [
        {"time": "09:00", "title": "Ops standup"},
        {"time": "11:30", "title": "Client walk-through", "detail": "Bank HQ perimeter", "tone": "attention"},
        {"time": "15:00", "title": "Tender review"}]},
    "person": {"block": "person", "name": "Adewale Adebanjo", "role": "Founder, Starrdam Intelligence",
               "detail": "Next: client walk-through at 11:30"},
    "chips": {"block": "chips", "items": [
        {"text": "Aviation", "tone": "neutral"}, {"text": "Energy", "tone": "neutral"},
        {"text": "At risk", "tone": "bad"}, {"text": "On track", "tone": "good"}]},
    "text": {"block": "text", "text": "No new competitive signals since yesterday’s brief."},
    "quote": {"block": "quote", "text": "Secure, discreet, intelligence-led.", "cite": "Starrdam positioning"},
    "facts": {"block": "facts", "items": [
        {"label": "Operations supported", "value": "100+"},
        {"label": "Deployment readiness", "value": "200+"},
        {"label": "Sectors", "value": "6"}]},
}


def sample_blocks() -> list[dict]:
    """Every block type, validated, in a stable order."""
    return [validate_block(_RAW[t]) for t in BLOCK_TYPES]


# One realistic example of each widget (Starrdam-flavoured), for the style page.
_RAW_WIDGETS = [
    {"type": "stat", "title": "Revenue this year", "label": "Revenue",
     "value": "$184,000", "delta": "+12% vs last year", "tone": "good",
     "hint": "Through November", "source": "accounts",
     "asks": ["What changed since last month?", "Which sector drove it?"]},
    {"type": "brief", "title": "Competitive brief",
     "text": "Tantita's Jan VTOL move still owns the drone narrative; aviation stays uncontested.",
     "points": ["Call NCAA", "Aviation wedge", "No new signals"], "source": "daily"},
    {"type": "next-up", "title": "Next up",
     "events": [{"time": "09:00", "title": "Ops standup"},
                {"time": "11:30", "title": "Client walk-through", "detail": "Bank HQ perimeter", "tone": "attention"},
                {"time": "15:00", "title": "Tender review"}], "source": "calendar"},
    {"type": "inbox", "title": "Needs a reply",
     "items": [{"subject": "NCAA tender query", "from": "aviation@ncaa", "when": "2h", "urgent": True},
               {"subject": "Drone MRO quote", "from": "ops", "when": "1d"}], "source": "mail"},
    {"type": "tasks", "title": "Tasks",
     "items": [{"title": "Sign off MRO quote", "due": "today", "urgent": True},
               {"title": "Call Port Harcourt lead", "due": "3d"}]},
    {"type": "opportunities", "title": "Opportunities",
     "items": [{"title": "Aviation security", "detail": "Uncontested vs Tantita", "meta": "high"},
               {"title": "Counter-UAS", "detail": "Defensive drone niche", "meta": "open"}]},
    {"type": "sector", "title": "Sector spotlight", "sector": "Aviation",
     "note": "22 NCAA airports, fragmented guarding, zero integrated intel."},
    {"type": "risk-meter", "title": "Threat level", "value": 38,
     "caption": "Moderate — Gulf of Guinea", "tone": "attention"},
    {"type": "pipeline", "title": "Pipeline",
     "deals": [{"name": "Aviation Authority", "stage": "Proposal", "value": "$48k"},
               {"name": "Port Security", "stage": "Negotiation", "value": "$120k"},
               {"name": "Bank HQ", "stage": "Qualified", "value": "$32k"}], "source": "crm"},
    {"type": "goal", "title": "Q4 target", "value": 68, "caption": "68% of $250k", "tone": "good"},
    {"type": "custom", "title": "Readiness", "blocks": [
        {"block": "facts", "items": [{"label": "Operatives", "value": "200+"},
                                     {"label": "Coverage", "value": "50+ areas"}]},
        {"block": "chips", "items": [{"text": "24/7", "tone": "good"}, {"text": "Licensed"}]},
    ]},
]


def sample_widgets() -> list[dict]:
    """Every widget type, validated + expanded into blocks, for the style page."""
    from .widgets import build_board
    return build_board(_RAW_WIDGETS, now="just now")
