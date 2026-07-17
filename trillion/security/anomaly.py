"""
Per-tool anomaly detection — sliding-window safety caps.

Threat: tool-frequency abuse. A runaway loop or a compromised heartbeat firing a
mutating tool hundreds of times. Each tool gets an in-memory sliding window; a
dispatch that would exceed the cap is blocked and NOT recorded, so the cap is a
true ceiling rather than a one-strike lockout.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

# tool -> (max_calls, window_seconds). Tools not listed are uncapped.
CAPS: dict[str, tuple[int, int]] = {
    "delete_reminder": (3, 86400),    # 3 / day — destructive
    "forget_fact":     (3, 86400),    # 3 / day — destructive
    "draft_message":   (10, 3600),    # 10 / hour — outbound-ish
    "web_search":      (30, 3600),    # 30 / hour — external + paid
    "add_reminder":    (40, 3600),
    "remember_fact":   (40, 3600),
    "update_memory":   (40, 3600),
}

_calls: dict[str, deque] = defaultdict(deque)


def check_and_record(tool_name: str) -> tuple[bool, dict]:
    """Return (allowed, info). Records the call only when allowed, so a blocked
    call doesn't consume the window."""
    cap = CAPS.get(tool_name)
    if cap is None:
        return True, {}
    limit, window = cap
    now = time.monotonic()
    dq = _calls[tool_name]
    while dq and now - dq[0] > window:
        dq.popleft()
    if len(dq) >= limit:
        return False, {"tool": tool_name, "count": len(dq), "limit": limit, "window_seconds": window}
    dq.append(now)
    return True, {"tool": tool_name, "count": len(dq), "limit": limit, "window_seconds": window}


def blocked_message(info: dict) -> str:
    return (
        f"Rate cap reached for '{info['tool']}': {info['count']}/{info['limit']} "
        f"within {info['window_seconds']}s. This is a safety ceiling to stop runaway "
        f"loops — wait for the window to clear, then try again."
    )


def caps_summary() -> dict:
    return {"tools_capped": len(CAPS), "caps": CAPS}
