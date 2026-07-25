"""
Memory tools over the file-backed store: remember, recall, forget, list.

The guidance about *what* is worth remembering lives in the tool descriptions,
because that is what the model reads when deciding to call them. Forgetting is
confirmation-gated — it deletes a file.
"""
from __future__ import annotations

from .memory_store import TYPES, FileMemoryStore

_REMEMBER_DESC = (
    "Save a durable fact worth keeping across future sessions — something the "
    "user taught you, a correction they made, a lasting preference, or a "
    "decision on one of their projects. Do NOT save transient task state, the "
    "current conversation, or anything already knowable from the code/config — "
    "and NEVER save secrets, passwords, tokens, or other people's private data. "
    "`hook` is a one-line searchable summary; `body` should add why it matters "
    "and how to apply it. `type` is one of: user (who they are), feedback (how "
    "they want you to work), project (ongoing work), reference (a pointer to an "
    "external resource)."
)

_RECALL_DESC = (
    "Search your long-term memories for anything relevant to a query. Use this "
    "when you're unsure whether you already know something about the user. "
    "Returns the closest matches (semantic when available, keyword otherwise)."
)

_FORGET_DESC = "Delete a stored memory by its id when it is wrong or no longer true."


def register_file_memory_tools(registry, store: FileMemoryStore | None = None) -> None:
    store = store or FileMemoryStore()

    def remember(hook: str, body: str = "", type: str = "user") -> str:
        try:
            m = store.add(hook=hook, body=body or hook, mtype=type, source="conversation")
            return f"Remembered [{m.type}]: {m.hook}  (id: {m.slug})"
        except Exception as e:
            return f"Couldn't remember that: {e}"

    def recall(query: str) -> str:
        from .memory_recall import recall as _recall
        res = _recall(query, store)
        if not res.memories:
            return "No matching memories."
        lines = [f"- [{m.type}] {m.hook} (id: {m.slug})" for m in res.memories]
        return f"({res.mode} recall)\n" + "\n".join(lines)

    def forget(id: str) -> str:
        return "Forgotten." if store.delete(id) else f"No memory with id {id!r}."

    def list_memories() -> str:
        mems = store.all()
        if not mems:
            return "No memories stored yet."
        out = []
        for t in TYPES:
            group = [m for m in mems if m.type == t]
            if not group:
                continue
            out.append(f"{t}:")
            out += [f"  - {m.hook} (id: {m.slug})" for m in group]
        return "\n".join(out)

    registry.register("remember", _REMEMBER_DESC, {
        "type": "object",
        "properties": {
            "hook": {"type": "string", "description": "one-line summary of the fact"},
            "body": {"type": "string", "description": "the fact plus why it matters / how to apply it"},
            "type": {"type": "string", "enum": list(TYPES), "description": "memory category"},
        },
        "required": ["hook"],
    }, remember, requires_confirmation=False)

    registry.register("recall", _RECALL_DESC, {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "what to look for"}},
        "required": ["query"],
    }, recall, requires_confirmation=False)

    registry.register("forget", _FORGET_DESC, {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "the memory id (slug) to delete"}},
        "required": ["id"],
    }, forget, requires_confirmation=True)

    registry.register("list_memories", "List all stored long-term memories, grouped by type.",
                      {"type": "object", "properties": {}}, list_memories, requires_confirmation=False)
