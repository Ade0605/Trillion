"""Reminders tool — add, list, and complete reminders stored in data/reminders.json."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

_DATA = Path(__file__).parent.parent.parent / "data" / "reminders.json"


def _load() -> list[dict]:
    if not _DATA.exists():
        return []
    return json.loads(_DATA.read_text(encoding="utf-8"))


def _save(items: list[dict]) -> None:
    _DATA.parent.mkdir(parents=True, exist_ok=True)
    _DATA.write_text(json.dumps(items, indent=2), encoding="utf-8")


def add_reminder(text: str, due: str = "") -> str:
    """Add a reminder. 'due' is optional free-text date/time."""
    items = _load()
    item = {
        "id": str(uuid.uuid4())[:8],
        "text": text,
        "due": due,
        "done": False,
        "created_at": datetime.now().isoformat(),
    }
    items.append(item)
    _save(items)
    due_str = f" (due: {due})" if due else ""
    return f"Reminder added: \"{text}\"{due_str} [id: {item['id']}]"


def list_reminders(include_done: bool = False) -> str:
    items = _load()
    visible = [i for i in items if include_done or not i["done"]]
    if not visible:
        return "No reminders found." if include_done else "No pending reminders."
    lines = []
    for i in visible:
        status = "[x]" if i["done"] else "[ ]"
        due = f" — due: {i['due']}" if i.get("due") else ""
        lines.append(f"{status} [{i['id']}] {i['text']}{due}")
    return "\n".join(lines)


def complete_reminder(id: str) -> str:
    items = _load()
    for item in items:
        if item["id"] == id:
            item["done"] = True
            _save(items)
            return f"Marked done: \"{item['text']}\""
    return f"No reminder found with id '{id}'."


def delete_reminder(id: str) -> str:
    items = _load()
    before = len(items)
    items = [i for i in items if i["id"] != id]
    if len(items) == before:
        return f"No reminder found with id '{id}'."
    _save(items)
    return f"Reminder {id} deleted."


def register_reminders(registry) -> None:
    registry.register(
        name="add_reminder",
        description="Add a reminder or todo item. Optionally include a due date or time as free text.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "What to remember"},
                "due": {"type": "string", "description": "Optional due date/time, e.g. 'tomorrow 9am' or '2026-07-01'"},
            },
            "required": ["text"],
        },
        fn=add_reminder,
    )
    registry.register(
        name="list_reminders",
        description="List pending (or all) reminders. Pass include_done=true to see completed ones too.",
        input_schema={
            "type": "object",
            "properties": {
                "include_done": {"type": "boolean", "description": "Include completed reminders", "default": False},
            },
        },
        fn=list_reminders,
    )
    registry.register(
        name="complete_reminder",
        description="Mark a reminder as done by its id.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The reminder id (shown in brackets when listing)"},
            },
            "required": ["id"],
        },
        fn=complete_reminder,
    )
    registry.register(
        name="delete_reminder",
        description="Permanently delete a reminder by its id.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The reminder id to delete"},
            },
            "required": ["id"],
        },
        fn=delete_reminder,
        requires_confirmation=True,
    )
