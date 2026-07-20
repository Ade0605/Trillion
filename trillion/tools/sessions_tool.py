"""
Claude Code session tool — read-only view of recent coding sessions.
"""
from __future__ import annotations

_SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {
            "type": "integer",
            "description": "How many recent sessions to return. Default 5, max 20.",
        }
    },
}

_DESC = (
    "List the user's most recent Claude Code sessions — title, project, and how "
    "long ago each was active. Read-only."
)


def list_recent_sessions(limit: int = 5) -> str:
    from trillion.claude_sessions import recent_sessions, summarise

    try:
        limit = int(limit or 5)
    except (TypeError, ValueError):
        limit = 5
    limit = max(1, min(limit, 20))

    try:
        sessions = recent_sessions(limit)
    except Exception as e:
        return f"Couldn't read Claude Code sessions ({type(e).__name__})."
    return summarise(sessions)


def register(registry) -> None:
    registry.register("list_recent_sessions", _DESC, _SCHEMA, list_recent_sessions,
                      requires_confirmation=False)
