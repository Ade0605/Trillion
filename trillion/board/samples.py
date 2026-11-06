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
