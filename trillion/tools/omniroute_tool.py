"""
OmniRoute status tool — read-only view of the router's health and token usage.
"""
from __future__ import annotations

_SCHEMA = {"type": "object", "properties": {}}

_DESC = (
    "Check OmniRoute (the local LLM router): whether it's running, its version, "
    "how many tokens have been used, and which model was routed most recently. "
    "Read-only."
)


def omniroute_status() -> str:
    try:
        from trillion.omniroute import status, summarise
        return summarise(status())
    except Exception as e:
        return f"Couldn't read OmniRoute status ({type(e).__name__})."


def register(registry) -> None:
    registry.register("omniroute_status", _DESC, _SCHEMA, omniroute_status,
                      requires_confirmation=False)
