"""
readstate — Layer 4. Once a page has been read this turn, anything with side
effects (writing a file, sending a message, saving a memory, spending money)
must wait for the user's explicit approval. This is the flag the agent checks.

Also labels any memory saved after a read as coming from read content, not from
the user — so a page can't plant a durable instruction that outranks the user.
"""
from __future__ import annotations

MEMORY_READ_LABEL = "(heard from a web page I read, not from the user)"


class ReadState:
    """Per-turn: has the agent read outside web content this turn?"""

    def __init__(self) -> None:
        self._read = False

    def mark_read(self) -> None:
        self._read = True

    @property
    def has_read(self) -> bool:
        return self._read

    def reset(self) -> None:
        """Call at the start of each user turn."""
        self._read = False


# Tools that only READ are safe to run after a page was read. Everything else
# (writing, sending, saving, spending) must wait for the user's approval once
# outside content has entered the turn. Bias is toward gating: unknown → gated.
_SAFE_PREFIXES = ("list_", "read_", "get_", "search_")
_SAFE_NAMES = frozenset({
    "web_fetch", "web_search", "show_panel", "system_status",
    "omniroute_status", "list_recent_sessions", "verify_identity",
})


def is_side_effect_after_read(name: str) -> bool:
    """True if running `name` after reading a page should require approval."""
    n = (name or "").strip().lower()
    if n in _SAFE_NAMES or n.startswith(_SAFE_PREFIXES):
        return False
    return True


def label_read_memory(body: str) -> str:
    """Prefix a memory saved after reading so it's never mistaken for the user."""
    b = (body or "").strip()
    if MEMORY_READ_LABEL in b:
        return b
    return f"{MEMORY_READ_LABEL} {b}".strip()
