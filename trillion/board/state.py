"""
state — the live board: the widgets currently on screen, by id. File-backed
(data/board.json, git-ignored) so the tools that write it and the page route
that reads it share one source of truth, and the board survives a restart.

The model never sees this file; it calls the show/update/remove tools, the
server validates + expands each widget, assigns the id, and stamps the time.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from . import caps
from .widgets import build_widget, WidgetError

_PATH = Path(__file__).parent.parent.parent / "data" / "board.json"
_LOCK = threading.Lock()


def _now_label() -> str:
    return "just now"


class BoardStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _PATH

    def _read(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write(self, widgets: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(widgets, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    def snapshot(self) -> list[dict]:
        return self._read()

    def show(self, widgets: object, *, replace: bool = True) -> list[dict]:
        """Put widgets on the board (replacing all, or adding). Returns the new
        set as [{id, title}] summaries. Raises WidgetError naming the field."""
        if not isinstance(widgets, list):
            raise WidgetError("widgets must be a list")
        built = []
        for raw in widgets:
            w = build_widget(raw, now=_now_label())
            w["id"] = uuid.uuid4().hex[:8]
            built.append(w)
        with _LOCK:
            current = [] if replace else self._read()
            current = (current + built)[: caps.MAX_WIDGETS]
            self._write(current)
        return [{"id": w["id"], "title": w.get("title", w["type"])} for w in built]

    def update(self, widget_id: str, widget: object) -> dict | None:
        """Replace one widget by id with a freshly built one, keeping its id."""
        w = build_widget(widget, now=_now_label())
        w["id"] = widget_id
        with _LOCK:
            current = self._read()
            for i, existing in enumerate(current):
                if existing.get("id") == widget_id:
                    current[i] = w
                    self._write(current)
                    return {"id": widget_id, "title": w.get("title", w["type"])}
        return None

    def remove(self, ids: object) -> list[str]:
        """Remove widgets by id. Returns the ids actually removed."""
        want = {ids} if isinstance(ids, str) else set(ids or [])
        with _LOCK:
            current = self._read()
            kept = [w for w in current if w.get("id") not in want]
            removed = [w["id"] for w in current if w.get("id") in want]
            self._write(kept)
        return removed

    def clear(self) -> None:
        with _LOCK:
            self._write([])
