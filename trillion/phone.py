"""
Phone PWA support — the turn-text store for non-evicting TTS lookup.

iOS Safari's <audio> element GETs the audio source twice (metadata probe, then
play). So the text behind a turn_id must survive the first read: eviction is
TTL-driven and lazy-on-write, never on read.
"""
from __future__ import annotations

import threading
import time
import uuid

_TTL = 600  # seconds a turn's text stays fetchable
_lock = threading.Lock()
_store: dict[str, tuple[str, float]] = {}


def record_turn_text(text: str) -> str:
    """Store reply text under a fresh turn_id; prune expired entries lazily."""
    now = time.monotonic()
    turn_id = uuid.uuid4().hex[:16]
    with _lock:
        for k in [k for k, (_, exp) in _store.items() if exp < now]:
            _store.pop(k, None)
        _store[turn_id] = (text, now + _TTL)
    return turn_id


def record_turn_text_as(turn_id: str, text: str) -> str:
    """Store text under a caller-chosen id (used for per-sentence segments,
    keyed `<base_turn_id>::<seq>`), pruning expired entries lazily."""
    now = time.monotonic()
    with _lock:
        for k in [k for k, (_, exp) in _store.items() if exp < now]:
            _store.pop(k, None)
        _store[turn_id] = (text, now + _TTL)
    return turn_id


def get_turn_text(turn_id: str) -> str | None:
    """Return the text for a turn_id, or None if missing/expired. Never deletes
    on read — the <audio> element's second GET must still succeed."""
    now = time.monotonic()
    with _lock:
        entry = _store.get(turn_id)
    if not entry or entry[1] < now:
        return None
    return entry[0]
