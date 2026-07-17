"""
Kill switch — the "stop this thing now" button.

Threat: an agent gone wrong (runaway loop, compromised key, injection that got
through). Setting TRILLION_KILL_SWITCH pauses every tool call and the heartbeat
tick on the next dispatch — no restart needed.

    export TRILLION_KILL_SWITCH=true    # halt
    export TRILLION_KILL_SWITCH=false   # resume
"""
from __future__ import annotations

import os

_TRUE = {"true", "1", "yes", "on"}


def is_active() -> bool:
    return os.environ.get("TRILLION_KILL_SWITCH", "").strip().lower() in _TRUE


def blocked_response(tool_name: str = "") -> str:
    return (
        "Trillion is paused (kill switch active). No tools will run. "
        "Set TRILLION_KILL_SWITCH=false to resume."
    )
