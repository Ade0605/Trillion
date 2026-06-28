"""
Long-term memory store — survives restarts.
Backed by data/memory.json: one fact per entry, human-readable and editable.
Facts are background knowledge injected into the system prompt, not commands.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

_DATA = Path(__file__).parent.parent / "data" / "memory.json"


class MemoryStore:
    def __init__(self) -> None:
        _DATA.parent.mkdir(parents=True, exist_ok=True)
        if not _DATA.exists():
            _DATA.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict]:
        return json.loads(_DATA.read_text(encoding="utf-8"))

    def _save(self, facts: list[dict]) -> None:
        _DATA.write_text(json.dumps(facts, indent=2), encoding="utf-8")

    def load_relevant(self, context: str = "") -> list[str]:
        """Return fact statements to inject into the system prompt."""
        facts = self._load()
        return [f["statement"] for f in facts if not f.get("deleted")]

    def add_fact(self, statement: str) -> str:
        facts = self._load()
        entry = {
            "id": str(uuid.uuid4())[:8],
            "statement": statement,
            "created_at": datetime.now().isoformat(),
            "deleted": False,
        }
        facts.append(entry)
        self._save(facts)
        return f"Remembered: \"{statement}\" [id: {entry['id']}]"

    def update_fact(self, id: str, new_statement: str) -> str:
        facts = self._load()
        for f in facts:
            if f["id"] == id:
                f["statement"] = new_statement
                f["updated_at"] = datetime.now().isoformat()
                self._save(facts)
                return f"Updated memory {id}: \"{new_statement}\""
        return f"No memory found with id '{id}'."

    def delete_fact(self, id: str) -> str:
        facts = self._load()
        for f in facts:
            if f["id"] == id:
                f["deleted"] = True
                self._save(facts)
                return f"Forgot: \"{f['statement']}\""
        return f"No memory found with id '{id}'."

    def list_facts(self) -> str:
        facts = [f for f in self._load() if not f.get("deleted")]
        if not facts:
            return "No memories stored yet."
        return "\n".join(f"[{f['id']}] {f['statement']}" for f in facts)


def register_memory_tools(registry, memory: MemoryStore) -> None:
    registry.register(
        name="remember_fact",
        description=(
            "Remember a fact about the user or their preferences for future conversations. "
            "Write it as a plain statement, e.g. 'User prefers morning meetings' or 'User's name is Bami'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "statement": {"type": "string", "description": "The fact to remember, as a plain statement"},
            },
            "required": ["statement"],
        },
        fn=memory.add_fact,
    )
    registry.register(
        name="update_memory",
        description="Correct or update a previously stored memory by its id.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The memory id to update"},
                "new_statement": {"type": "string", "description": "The corrected statement"},
            },
            "required": ["id", "new_statement"],
        },
        fn=memory.update_fact,
    )
    registry.register(
        name="forget_fact",
        description="Remove a stored memory that is wrong or no longer relevant, by its id.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The memory id to delete"},
            },
            "required": ["id"],
        },
        fn=memory.delete_fact,
    )
    registry.register(
        name="list_memories",
        description="List all memories currently stored about the user.",
        input_schema={"type": "object", "properties": {}},
        fn=memory.list_facts,
    )
