"""
Heartbeat check: generate a daily morning brief of today's reminders.
Fires once per day at the configured trigger_hour.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).parent.parent.parent / "data" / "reminders.json"


def _calendar_lines() -> str:
    """Today's calendar, or '' when not configured/reachable. Never raises —
    a calendar outage must not suppress the reminders half of the brief."""
    try:
        from trillion import calendar_yahoo as cal
    except Exception:
        return ""
    if not cal.configured():
        return ""
    try:
        events = cal.todays_events()
    except Exception:
        return "\n\nCalendar: couldn't reach Yahoo just now."
    if not events:
        return "\n\nCalendar: nothing scheduled today."
    body = "\n".join(f"  • {e.line()}" for e in events)
    return f"\n\nCalendar today ({len(events)}):\n{body}"


def run() -> list[dict] | None:
    cal_part = _calendar_lines()

    pending = []
    if _DATA.exists():
        try:
            items = json.loads(_DATA.read_text(encoding="utf-8"))
            pending = [i for i in items if not i.get("done")]
        except Exception:
            pending = []

    if not pending and not cal_part:
        return None

    if not pending:
        return [{"message": f"Good morning!{cal_part}", "priority": "low"}]

    lines = "\n".join(f"  • {i['text']}" + (f" (due: {i['due']})" if i.get("due") else "") for i in pending)
    return [
        {
            "message": f"Good morning! You have {len(pending)} pending reminder(s):\n{lines}{cal_part}",
            "priority": "low",
        }
    ]
