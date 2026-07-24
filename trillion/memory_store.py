"""
Long-term memory as human-readable files — the source of truth.

Each memory is one markdown file under `data/memory/<slug>.md`:

    ---
    type: user
    hook: User is based in London
    created: 2026-06-29T13:04:11
    source: conversation
    ---

    User is based in London.

    **Why it matters:** ...
    **How to apply:** ...

The **hook** is the one-line searchable summary; the **body** captures the fact
plus why it matters and how to apply it. The **type** is a small fixed set —
`user` (who they are), `feedback` (how they want Trillion to work), `project`
(ongoing work), `reference` (pointers to external things) — because the type
shapes when a memory is worth recalling.

Files are the truth: they can be opened, edited, or deleted by hand and are
portable out of this system. `INDEX.md` is a derived, rebuildable listing of the
hooks — never the source of truth. Any embedding index (Tier 6) is likewise
derived. `data/` is git-ignored, so private facts never enter the repo.

Never stores secrets: the caller decides what to remember; this only writes what
it is given, and the prompt guidance (Tier 7) forbids credentials/PII.
"""
from __future__ import annotations

import datetime as _dt
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

_DIR = Path(__file__).parent.parent / "data" / "memory"
_INDEX = _DIR / "INDEX.md"

TYPES = ("user", "feedback", "project", "reference")
DEFAULT_TYPE = "user"

_lock = threading.RLock()


@dataclass
class Memory:
    slug: str
    type: str
    hook: str
    body: str
    created: str = ""
    source: str = ""
    extra: dict = field(default_factory=dict)

    def render(self) -> str:
        """Full markdown file content (frontmatter + body)."""
        fm = [f"type: {self.type}", f"hook: {self.hook}"]
        if self.created:
            fm.append(f"created: {self.created}")
        if self.source:
            fm.append(f"source: {self.source}")
        for k, v in self.extra.items():
            fm.append(f"{k}: {v}")
        return "---\n" + "\n".join(fm) + "\n---\n\n" + self.body.strip() + "\n"


def _slugify(hook: str, existing: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", hook.lower()).strip("-")[:50] or "memory"
    slug = base
    n = 2
    while slug in existing:
        slug = f"{base}-{n}"
        n += 1
    return slug


def _parse(text: str) -> tuple[dict, str]:
    """Split a memory file into (frontmatter dict, body). Tolerant of missing or
    malformed frontmatter — a hand-edited file must never crash the loader."""
    meta: dict = {}
    body = text
    if text.lstrip().startswith("---"):
        rest = text.lstrip()[3:]
        end = rest.find("\n---")
        if end != -1:
            block = rest[:end]
            body = rest[end + 4:].lstrip("\n")
            for line in block.splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                k, _, v = line.partition(":")
                meta[k.strip().lower()] = v.strip()
    return meta, body.strip()


class FileMemoryStore:
    def __init__(self, root: Path | None = None) -> None:
        self.dir = root or _DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    # ---- read -------------------------------------------------------------- #

    def all(self) -> list[Memory]:
        out: list[Memory] = []
        for p in sorted(self.dir.glob("*.md")):
            if p.name == "INDEX.md":
                continue
            try:
                meta, body = _parse(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            mtype = (meta.get("type") or DEFAULT_TYPE).strip()
            if mtype not in TYPES:
                mtype = DEFAULT_TYPE
            known = {"type", "hook", "created", "source"}
            out.append(Memory(
                slug=p.stem,
                type=mtype,
                hook=meta.get("hook", "") or (body.splitlines()[0] if body else p.stem),
                body=body,
                created=meta.get("created", ""),
                source=meta.get("source", ""),
                extra={k: v for k, v in meta.items() if k not in known},
            ))
        return out

    def get(self, slug: str) -> Memory | None:
        return next((m for m in self.all() if m.slug == slug), None)

    def count(self) -> int:
        return sum(1 for p in self.dir.glob("*.md") if p.name != "INDEX.md")

    # ---- write ------------------------------------------------------------- #

    def add(self, hook: str, body: str, mtype: str = DEFAULT_TYPE,
            source: str = "", created: str | None = None) -> Memory:
        hook = " ".join((hook or "").split()).strip()
        if not hook:
            raise ValueError("a memory needs a one-line hook")
        if mtype not in TYPES:
            mtype = DEFAULT_TYPE
        with _lock:
            existing = {p.stem for p in self.dir.glob("*.md")}
            slug = _slugify(hook, existing)
            mem = Memory(
                slug=slug, type=mtype, hook=hook, body=(body or hook).strip(),
                created=created or _dt.datetime.now().isoformat(timespec="seconds"),
                source=source,
            )
            (self.dir / f"{slug}.md").write_text(mem.render(), encoding="utf-8")
            self._write_index()
        return mem

    def delete(self, slug: str) -> bool:
        with _lock:
            p = self.dir / f"{slug}.md"
            if not p.exists():
                return False
            p.unlink()
            self._write_index()
            return True

    def update(self, slug: str, *, hook: str | None = None,
               body: str | None = None, mtype: str | None = None) -> Memory | None:
        with _lock:
            mem = self.get(slug)
            if not mem:
                return None
            if hook is not None:
                mem.hook = " ".join(hook.split()).strip()
            if body is not None:
                mem.body = body.strip()
            if mtype is not None and mtype in TYPES:
                mem.type = mtype
            (self.dir / f"{slug}.md").write_text(mem.render(), encoding="utf-8")
            self._write_index()
            return mem

    # ---- index (derived, rebuildable) ------------------------------------- #

    def _write_index(self) -> None:
        mems = self.all()
        lines = ["# Memory Index", "",
                 "_Derived from the files in this directory — rebuildable, never "
                 "the source of truth._", ""]
        if not mems:
            lines.append("_No memories yet._")
        for t in TYPES:
            group = [m for m in mems if m.type == t]
            if not group:
                continue
            lines.append(f"## {t}")
            for m in sorted(group, key=lambda m: m.slug):
                lines.append(f"- [{m.hook}]({m.slug}.md)")
            lines.append("")
        _INDEX_path = self.dir / "INDEX.md"
        _INDEX_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def rebuild_index(self) -> int:
        with _lock:
            self._write_index()
        return self.count()


def migrate_from_json(store: FileMemoryStore, json_path: Path | None = None) -> int:
    """One-time import of the legacy flat data/memory.json into typed files.

    The old file is left untouched on disk as a fallback — this only reads it.
    Returns the number of memories imported (0 if already migrated or absent).
    """
    import json

    json_path = json_path or (Path(__file__).parent.parent / "data" / "memory.json")
    if not json_path.exists() or store.count() > 0:
        return 0
    try:
        facts = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return 0

    imported = 0
    for f in facts:
        if f.get("deleted"):
            continue
        statement = (f.get("statement") or "").strip()
        if not statement:
            continue
        hook = statement if len(statement) <= 80 else statement[:77] + "…"
        store.add(hook=hook, body=statement, mtype="user",
                  source="migrated from memory.json",
                  created=f.get("created_at") or None)
        imported += 1
    return imported
