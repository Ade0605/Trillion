"""
Session-end memory extractor + an approval queue.

When a conversation ends, a cheap model call reads the transcript and proposes
durable memories worth keeping. It does NOT write them: proposals land in a
pending queue that the user approves at /memory. Silent background writes have
bitten this user before, so nothing enters long-term memory without a click —
the same approval-gate discipline as the agent factory.

Guardrails baked into the prompt: skip transient state, small talk, and testing
sessions; never propose secrets or other people's private data; dedupe against
what's already stored.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from pathlib import Path

from .memory_store import TYPES, FileMemoryStore

_PENDING = Path(__file__).parent.parent / "data" / "memory_pending.json"
_lock = threading.RLock()

MIN_USER_TURNS = 2          # below this it's not a real conversation
MAX_PROPOSALS = 6

_SYSTEM = (
    "You extract durable, long-term memories from a conversation transcript for a "
    "personal assistant. Return ONLY facts worth remembering across future "
    "sessions: things the user taught you about themselves, lasting preferences, "
    "corrections they made, or decisions on their projects.\n\n"
    "NEVER extract: transient task state, the current conversation's mechanics, "
    "anything already obvious from tooling, small talk, or — absolutely never — "
    "secrets, passwords, tokens, API keys, or other people's private data.\n\n"
    "If the transcript is just testing, chit-chat, or has nothing durable, return "
    "an empty list.\n\n"
    "Reply with a JSON array (no prose) of objects: "
    '{"hook": "<one-line summary>", "body": "<the fact + why it matters>", '
    '"type": "user|feedback|project|reference"}.'
)


def _transcript(messages: list[dict]) -> tuple[str, int]:
    """Render user/assistant text turns to plain text; returns (text, user_turns).
    Tool payloads are skipped — they're re-derivable and the highest-risk thing
    to accidentally memorialise."""
    lines = []
    user_turns = 0
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if not isinstance(content, str):
            continue                     # skip tool_use / tool_result rounds
        if role == "user":
            user_turns += 1
            lines.append(f"User: {content}")
        elif role == "assistant":
            lines.append(f"Assistant: {content}")
    return "\n".join(lines), user_turns


def _parse_json_array(text: str) -> list[dict]:
    if not text:
        return []
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except Exception:
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        hook = " ".join(str(item.get("hook", "")).split()).strip()
        if not hook:
            continue
        mtype = str(item.get("type", "user")).strip()
        if mtype not in TYPES:
            mtype = "user"
        out.append({"hook": hook, "body": str(item.get("body", "") or hook).strip(),
                    "type": mtype})
    return out[:MAX_PROPOSALS]


def _is_duplicate(hook: str, existing: list[str]) -> bool:
    """Reject a near-duplicate of an existing memory by token overlap on the
    hook. Cheap and offline; avoids piling up restatements."""
    from .memory_recall import _tokens
    ht = _tokens(hook)
    if not ht:
        return True
    for e in existing:
        et = _tokens(e)
        if et and len(ht & et) / max(len(ht | et), 1) >= 0.6:
            return True
    return False


def extract(messages: list[dict], store: FileMemoryStore | None = None,
            completer=None) -> list[dict]:
    """Propose durable memories from a transcript, deduped against the store.
    Returns [] for thin/testing sessions or when the model call fails."""
    store = store or FileMemoryStore()
    text, user_turns = _transcript(messages)
    if user_turns < MIN_USER_TURNS or len(text) < 40:
        return []

    if completer is None:
        from .provider import complete as completer

    raw = completer(
        f"Transcript:\n\n{text}\n\nExtract durable memories as a JSON array.",
        system=_SYSTEM,
    )
    proposals = _parse_json_array(raw)
    if not proposals:
        return []

    existing = [m.hook for m in store.all()]
    return [p for p in proposals if not _is_duplicate(p["hook"], existing)]


# --------------------------------------------------------------------------- #
# Pending-approval queue
# --------------------------------------------------------------------------- #

def _load_pending() -> list[dict]:
    try:
        return json.loads(_PENDING.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_pending(items: list[dict]) -> None:
    _PENDING.parent.mkdir(parents=True, exist_ok=True)
    _PENDING.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def enqueue(proposals: list[dict], source: str = "") -> int:
    if not proposals:
        return 0
    with _lock:
        items = _load_pending()
        existing_hooks = {i["hook"] for i in items}
        added = 0
        for p in proposals:
            if p["hook"] in existing_hooks:
                continue
            items.append({"id": uuid.uuid4().hex[:12], "hook": p["hook"],
                          "body": p["body"], "type": p["type"],
                          "source": source, "created": time.time()})
            added += 1
        _save_pending(items)
        return added


def list_pending() -> list[dict]:
    with _lock:
        return _load_pending()


def approve(item_id: str, store: FileMemoryStore | None = None) -> bool:
    store = store or FileMemoryStore()
    with _lock:
        items = _load_pending()
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            return False
        store.add(hook=item["hook"], body=item["body"], mtype=item["type"],
                  source=item.get("source") or "extracted, approved")
        _save_pending([i for i in items if i["id"] != item_id])
        return True


def reject(item_id: str) -> bool:
    with _lock:
        items = _load_pending()
        kept = [i for i in items if i["id"] != item_id]
        if len(kept) == len(items):
            return False
        _save_pending(kept)
        return True


def extract_and_enqueue(messages: list[dict], source: str = "") -> int:
    """Run the extractor and stage any proposals. Safe to call from a daemon
    thread — never raises."""
    try:
        return enqueue(extract(messages, source=source), source=source)
    except Exception:
        return 0
