"""
store — persist every meeting (question, seats, opinions, synthesis, cost, and
the citation snapshot) to data/board_meetings.json (git-ignored). A stored
meeting is self-contained: it renders without the dossiers.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

_PATH = Path(__file__).parent.parent.parent / "data" / "board_meetings.json"
_LOCK = threading.Lock()
_MAX = 200                      # keep the most recent N


def _read(path: Path) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_meeting(meeting: dict, *, path: Path | None = None) -> str:
    p = path or _PATH
    mid = uuid.uuid4().hex[:8]
    record = {"id": mid, **meeting}
    with _LOCK:
        meetings = _read(p)
        meetings.append(record)
        meetings = meetings[-_MAX:]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(meetings, ensure_ascii=False, indent=2), encoding="utf-8")
    return mid


def list_meetings(*, path: Path | None = None) -> list[dict]:
    return _read(path or _PATH)
