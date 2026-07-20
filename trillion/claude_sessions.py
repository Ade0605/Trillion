"""
Read Claude Code session transcripts — local, read-only.

Sessions live as JSONL under ~/.claude/projects/<slug>/<session-id>.jsonl. Each
line is one record; the useful ones are:

    ai-title      {"aiTitle": "..."}      generated session name
    last-prompt   {"lastPrompt": "..."}   most recent user prompt
    user/assistant                        turn records, carry cwd + timestamp

Files are scanned tail-first: only the last slice of each file is parsed for
titles, and recency comes from the filesystem mtime, so summarising 75 sessions
does not mean reading ~100MB of transcripts.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass
from pathlib import Path

def _default_root() -> Path:
    """Locate ~/.claude/projects for the *human* user.

    Path.home() is wrong under the Windows service: it runs as LocalSystem, whose
    home is C:\\Windows\\System32\\config\\systemprofile — no sessions there, so the
    brief silently reported none. Prefer an explicit override, then the real
    profile, then the newest C:/Users/<name>/.claude/projects.
    """
    env = os.environ.get("CLAUDE_PROJECTS_DIR", "").strip()
    if env:
        return Path(env)

    candidates = []
    home = Path.home() / ".claude" / "projects"
    if home.exists():
        candidates.append(home)

    for var in ("USERPROFILE", "HOME"):
        v = os.environ.get(var, "").strip()
        if v:
            p = Path(v) / ".claude" / "projects"
            if p.exists() and p not in candidates:
                candidates.append(p)

    if not candidates:
        users = Path(os.environ.get("SystemDrive", "C:") + "\\Users")
        if users.exists():
            found = []
            for d in users.iterdir():
                p = d / ".claude" / "projects"
                try:
                    if p.is_dir():
                        found.append((p.stat().st_mtime, p))
                except OSError:
                    continue
            found.sort(reverse=True)
            candidates += [p for _, p in found]

    return candidates[0] if candidates else home


SESSIONS_ROOT = _default_root()

# Only the tail of a file is read for metadata — transcripts reach tens of MB.
_TAIL_BYTES = 256 * 1024


@dataclass
class Session:
    session_id: str
    project: str
    title: str
    last_prompt: str
    modified: _dt.datetime
    size_kb: int
    turns: int

    def ago(self, now: _dt.datetime | None = None) -> str:
        now = now or _dt.datetime.now().astimezone()
        delta = now - self.modified
        secs = max(delta.total_seconds(), 0)
        if secs < 3600:
            m = int(secs // 60)
            return "just now" if m < 1 else f"{m} minute{'s' if m != 1 else ''} ago"
        if secs < 86400:
            h = int(secs // 3600)
            return f"{h} hour{'s' if h != 1 else ''} ago"
        d = int(secs // 86400)
        if d == 1:
            return "yesterday"
        return f"{d} days ago"

    def line(self) -> str:
        return f"{self.title} ({self.project}) — {self.ago()}"


def _pretty_project(slug: str) -> str:
    """'C--Users-delux-Bami-AI-Jarvis-trillion' -> 'trillion'."""
    name = slug.replace("--", "-").rstrip("-")
    parts = [p for p in name.split("-") if p]
    return parts[-1] if parts else slug


def _tail(path: Path, nbytes: int = _TAIL_BYTES) -> list[str]:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > nbytes:
                fh.seek(size - nbytes)
                fh.readline()          # discard the partial first line
            data = fh.read()
        return data.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _read_session(path: Path) -> Session | None:
    lines = _tail(path)
    if not lines:
        return None

    title = last_prompt = ""
    turns = 0
    # Walk backwards: the newest title/prompt wins and we can stop early.
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        kind = rec.get("type")
        if kind in ("user", "assistant"):
            turns += 1
        if not title and kind == "ai-title":
            title = str(rec.get("aiTitle") or "").strip()
        if not last_prompt and kind == "last-prompt":
            last_prompt = str(rec.get("lastPrompt") or "").strip()

    if not title:
        title = (last_prompt[:60] + "…") if len(last_prompt) > 60 else (last_prompt or "(untitled session)")

    try:
        stat = path.stat()
    except OSError:
        return None

    return Session(
        session_id=path.stem,
        project=_pretty_project(path.parent.name),
        title=" ".join(title.split()),
        last_prompt=" ".join(last_prompt.split())[:200],
        modified=_dt.datetime.fromtimestamp(stat.st_mtime).astimezone(),
        size_kb=stat.st_size // 1024,
        turns=turns,
    )


def recent_sessions(limit: int = 5, root: Path | None = None) -> list[Session]:
    """The N most recently active sessions, newest first."""
    root = root or _default_root()   # resolved per call so an env override applies
    if not root.exists():
        return []

    files = []
    for path in root.glob("*/*.jsonl"):
        try:
            files.append((path.stat().st_mtime, path))
        except OSError:
            continue
    files.sort(key=lambda t: t[0], reverse=True)

    out: list[Session] = []
    for _, path in files[: max(limit, 0) * 3]:   # headroom for unreadable files
        s = _read_session(path)
        if s:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def sessions_since(since: _dt.datetime, root: Path | None = None) -> list[Session]:
    """Every session touched at or after `since`, newest first."""
    root = root or _default_root()
    if not root.exists():
        return []

    out: list[Session] = []
    for path in root.glob("*/*.jsonl"):
        try:
            if _dt.datetime.fromtimestamp(path.stat().st_mtime).astimezone() < since:
                continue
        except OSError:
            continue
        s = _read_session(path)
        if s:
            out.append(s)
    out.sort(key=lambda s: s.modified, reverse=True)
    return out


def sessions_today(root: Path | None = None) -> list[Session]:
    start = _dt.datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    return sessions_since(start, root=root)


def day_report(sessions: list[Session], speakable: bool = False, top: int = 5) -> str:
    """End-of-day rollup: how much was worked on, where, and on what."""
    if not sessions:
        return ("No Claude Code sessions today." if speakable
                else "No Claude Code sessions today.")

    projects: dict[str, int] = {}
    for s in sessions:
        projects[s.project] = projects.get(s.project, 0) + 1
    turns = sum(s.turns for s in sessions)
    busiest = max(sessions, key=lambda s: s.turns)
    ranked = sorted(sessions, key=lambda s: s.turns, reverse=True)[:top]
    proj_names = sorted(projects, key=lambda p: projects[p], reverse=True)

    n = len(sessions)
    plural = "s" if n != 1 else ""

    if speakable:
        parts = [
            f"End of day. {n} Claude Code session{plural} today "
            f"across {len(projects)} project{'s' if len(projects) != 1 else ''}: "
            f"{', '.join(proj_names[:4])}.",
            f"Around {turns} turns in total.",
            f"Busiest was {busiest.title}, with {busiest.turns} turns.",
        ]
        if n > 1:
            others = [s.title for s in ranked[1:4]]
            if others:
                parts.append("Also worked on " + "; ".join(others) + ".")
        return " ".join(parts)

    lines = [
        f"Claude Code — end of day",
        f"  sessions: {n} across {len(projects)} project(s): "
        f"{', '.join(f'{p} ({projects[p]})' for p in proj_names)}",
        f"  total turns: {turns}",
        "",
        "Most active:",
    ]
    for i, s in enumerate(ranked, 1):
        lines.append(f"  {i}. {s.title} — {s.project} · {s.turns} turns · last {s.ago()}")
    return "\n".join(lines)


def summarise(sessions: list[Session], speakable: bool = False) -> str:
    """Rendered list. speakable=True drops IDs and shortens for text-to-speech."""
    if not sessions:
        return "No recent Claude Code sessions."

    if speakable:
        parts = [f"Your {len(sessions)} most recent Claude Code sessions."]
        for i, s in enumerate(sessions, 1):
            parts.append(f"{i}. {s.title}, in {s.project}, {s.ago()}.")
        return " ".join(parts)

    lines = []
    for i, s in enumerate(sessions, 1):
        lines.append(f"{i}. {s.title}")
        lines.append(f"   project: {s.project} · {s.ago()} · {s.turns} turns · {s.size_kb}KB")
    return "\n".join(lines)
