"""
edit — correcting the seats, with two rules learned expensively:

- Retire, never delete. Deleting an entry frees its id for reuse, and a later
  entry inheriting D3 silently re-points every stored citation at different
  content — a wrong attribution, worse than a broken link. Retiring keeps the id
  spoken for forever; the entry stays in the file, withheld from meetings.
- The server decides verification, never the user. Editing an entry's substance
  drops it to `user`, because the fact-check no longer covers what it now says —
  otherwise the editor becomes a way to stamp an unchecked claim as confirmed,
  the exact laundering this design exists to prevent.
"""
from __future__ import annotations

import re
from pathlib import Path

_SEATS_DIR = Path(__file__).parent / "seats"


class EditError(ValueError):
    pass


def _entry_block(text: str, entry_id: str) -> tuple[int, int]:
    """Return the (start, end) span of the '### D<id> …' block, or raise."""
    eid = entry_id.upper()
    m = re.search(rf"^###\s+{re.escape(eid)}\b.*$", text, re.MULTILINE | re.IGNORECASE)
    if not m:
        raise EditError(f"no entry {eid}")
    start = m.start()
    nxt = re.search(r"^(###|##)\s", text[m.end():], re.MULTILINE)
    end = m.end() + nxt.start() if nxt else len(text)
    return start, end


def _set_verification(block: str, state: str) -> str:
    if re.search(r"^verification\s*:", block, re.MULTILINE | re.IGNORECASE):
        return re.sub(r"^verification\s*:.*$", f"verification: {state}", block,
                      count=1, flags=re.MULTILINE | re.IGNORECASE)
    # no line yet — insert after the heading line
    head, _, rest = block.partition("\n")
    return f"{head}\nverification: {state}\n{rest}"


def _seat_path(slug: str, directory: Path | None) -> Path:
    p = (Path(directory) if directory else _SEATS_DIR) / f"{slug}.md"
    if not p.exists():
        raise EditError(f"no seat '{slug}'")
    return p


def retire_entry(slug: str, entry_id: str, *, directory: Path | None = None) -> None:
    """Retire a doctrine entry: keep it (id stays spoken-for) but withhold it from
    meetings. Stored citations to it still resolve."""
    p = _seat_path(slug, directory)
    text = p.read_text(encoding="utf-8")
    s, e = _entry_block(text, entry_id)
    p.write_text(text[:s] + _set_verification(text[s:e], "retired") + text[e:], encoding="utf-8")


def edit_entry(slug: str, entry_id: str, new_body: str, *, directory: Path | None = None) -> None:
    """Replace an entry's body. The server drops its verification to `user`,
    because the fact-check no longer covers the new text."""
    if not (new_body or "").strip():
        raise EditError("new body is empty")
    p = _seat_path(slug, directory)
    text = p.read_text(encoding="utf-8")
    s, e = _entry_block(text, entry_id)
    block = text[s:e]
    head = block.split("\n", 1)[0]
    source = re.search(r"^source\s*:.*$", block, re.MULTILINE | re.IGNORECASE)
    source_line = source.group(0) if source else "source: (user edit)"
    rebuilt = f"{head}\n{source_line}\nverification: user\n{new_body.strip()}\n\n"
    p.write_text(text[:s] + rebuilt + text[e:], encoding="utf-8")
