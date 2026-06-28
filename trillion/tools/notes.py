"""Notes tool — search plain-text files in the configured notes directory."""
from __future__ import annotations

from pathlib import Path

import yaml


def _notes_dir() -> Path:
    cfg_path = Path(__file__).parent.parent.parent / "config.yml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    rel = cfg.get("notes_dir", "notes")
    return Path(__file__).parent.parent.parent / rel


def search_notes(query: str) -> str:
    """Search notes files for lines matching the query (case-insensitive)."""
    notes_dir = _notes_dir()
    if not notes_dir.exists():
        return f"Notes directory '{notes_dir}' does not exist. Create it and add .txt or .md files."

    files = list(notes_dir.rglob("*.txt")) + list(notes_dir.rglob("*.md"))
    if not files:
        return "No note files found. Add .txt or .md files to the notes/ directory."

    q = query.lower()
    results: list[str] = []

    for path in sorted(files):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches = [
            f"  line {i+1}: {line.rstrip()}"
            for i, line in enumerate(text.splitlines())
            if q in line.lower()
        ]
        if matches:
            results.append(f"[{path.name}]\n" + "\n".join(matches))

    if not results:
        return f"No matches found for '{query}' in {len(files)} note file(s)."
    return f"Found matches in {len(results)} file(s):\n\n" + "\n\n".join(results)


def read_note(filename: str) -> str:
    """Read the full contents of a note file by name."""
    notes_dir = _notes_dir()
    candidates = list(notes_dir.rglob(filename))
    if not candidates:
        return f"No file named '{filename}' found in notes directory."
    return candidates[0].read_text(encoding="utf-8", errors="replace")


def list_notes() -> str:
    """List all note files available."""
    notes_dir = _notes_dir()
    if not notes_dir.exists():
        return "Notes directory does not exist."
    files = list(notes_dir.rglob("*.txt")) + list(notes_dir.rglob("*.md"))
    if not files:
        return "No note files found."
    return "\n".join(f.name for f in sorted(files))


def register_notes(registry) -> None:
    registry.register(
        name="search_notes",
        description="Search your local notes and documents for a keyword or phrase. Returns matching lines with file names.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The word or phrase to search for"},
            },
            "required": ["query"],
        },
        fn=search_notes,
    )
    registry.register(
        name="read_note",
        description="Read the full contents of a specific note file by filename.",
        input_schema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename to read, e.g. 'meeting-notes.md'"},
            },
            "required": ["filename"],
        },
        fn=read_note,
    )
    registry.register(
        name="list_notes",
        description="List all note files available in the notes directory.",
        input_schema={"type": "object", "properties": {}},
        fn=list_notes,
    )
