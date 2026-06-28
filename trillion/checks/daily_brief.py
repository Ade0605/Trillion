"""
Heartbeat check: generate a daily morning brief of today's reminders.
Fires once per day at the configured trigger_hour.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).parent.parent.parent / "data" / "reminders.json"


def run() -> list[dict] | None:
    if not _DATA.exists():
        return None

    items = json.loads(_DATA.read_text(encoding="utf-8"))
    pending = [i for i in items if not i.get("done")]
    if not pending:
        return [{"message": "Good morning! No pending reminders today.", "priority": "low"}]

    lines = "\n".join(f"  • {i['text']}" + (f" (due: {i['due']})" if i.get("due") else "") for i in pending)
    return [
        {
            "message": f"Good morning! You have {len(pending)} pending reminder(s):\n{lines}",
            "priority": "low",
        }
    ]
