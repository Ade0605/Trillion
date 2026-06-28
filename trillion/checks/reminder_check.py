"""
Heartbeat check: surface reminders due within the next hour.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

_DATA = Path(__file__).parent.parent.parent / "data" / "reminders.json"


def run() -> list[dict] | None:
    """
    Returns a list of notice dicts for due reminders, or None if nothing to surface.
    Each notice: {"message": str, "priority": "high"|"low"}
    """
    if not _DATA.exists():
        return None

    items = json.loads(_DATA.read_text(encoding="utf-8"))
    now = datetime.now()
    horizon = now + timedelta(hours=1)
    due_soon: list[str] = []

    for item in items:
        if item.get("done"):
            continue
        due_str = item.get("due", "").strip()
        if not due_str:
            continue
        # Try a handful of date formats
        parsed = _try_parse(due_str)
        if parsed and now <= parsed <= horizon:
            due_soon.append(f"\"{item['text']}\" (due: {due_str})")

    if not due_soon:
        return None

    return [
        {
            "message": f"Reminder due soon: {r}",
            "priority": "high",
        }
        for r in due_soon
    ]


def _try_parse(s: str) -> datetime | None:
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None
