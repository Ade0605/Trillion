"""
Working memory — the conversation, persisted across restarts.

The Agent's `conversation` was an in-memory list: it died on every restart (and
this server restarts on deploys, plus has a watchdog) and grew without bound
until the API refused it. This persists the active window to
`data/sessions/<id>.jsonl` after each turn and resolves the current session on
startup, so "what we were just doing" survives a restart. One shared thread
across every surface; a gap longer than IDLE_RESET_SECONDS starts a fresh one.

Design notes:
- **Snapshot, not append-log.** After each turn the *bounded, repaired* window
  is written whole. That deliberately drops turns that scrolled out of the
  window — long-term memory (a later tier) is what carries facts forward, not
  this. Working memory stays bounded by construction.
- **Never stores secrets.** It persists exactly the message dicts the Agent
  already holds — the same content sent to the model — and nothing more.
- `data/` is git-ignored, so the thread never lands in a public repo.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

_DIR = Path(__file__).parent.parent / "data" / "sessions"
IDLE_RESET_SECONDS = 1800  # 30 min without activity → a new session

_lock = threading.RLock()


class SessionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.dir = root or _DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, sid: str) -> Path:
        return self.dir / f"{sid}.jsonl"

    def _current_file(self) -> Path:
        return self.dir / "current.json"

    def _write_current(self, sid: str) -> None:
        self._current_file().write_text(
            json.dumps({"id": sid, "last_active": time.time()}), encoding="utf-8"
        )

    def resolve_active(self) -> tuple[str, bool]:
        """Return (session_id, is_new). Reuse the current session if it was
        active within the idle window and its file exists; else mint a new one."""
        now = time.time()
        with _lock:
            try:
                cur = json.loads(self._current_file().read_text(encoding="utf-8"))
                if (now - float(cur.get("last_active", 0)) < IDLE_RESET_SECONDS
                        and self._path(cur["id"]).exists()):
                    return cur["id"], False
            except Exception:
                pass
            sid = uuid.uuid4().hex[:16]
            self._write_current(sid)
            return sid, True

    def start_new(self) -> str:
        """Force a fresh session (used by /reset)."""
        with _lock:
            sid = uuid.uuid4().hex[:16]
            self._write_current(sid)
            return sid

    def load(self, sid: str) -> list[dict]:
        p = self._path(sid)
        if not p.exists():
            return []
        out: list[dict] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    def save(self, sid: str, messages: list[dict]) -> None:
        """Overwrite the session with the current window; bump last_active.

        Written to a temp file then replaced, so a crash mid-write can't leave a
        half-truncated session behind.
        """
        with _lock:
            tmp = self._path(sid).with_suffix(".jsonl.tmp")
            tmp.write_text(
                "\n".join(json.dumps(m, ensure_ascii=False) for m in messages),
                encoding="utf-8",
            )
            tmp.replace(self._path(sid))
            self._write_current(sid)

    def list_recent(self, n: int = 5) -> list[dict]:
        items = []
        for p in self.dir.glob("*.jsonl"):
            try:
                items.append((p.stat().st_mtime, p.stem))
            except OSError:
                continue
        items.sort(reverse=True)
        return [{"id": sid, "modified": mt} for mt, sid in items[:n]]
