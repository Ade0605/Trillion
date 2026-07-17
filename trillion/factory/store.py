"""
JSON-backed stores for the Factory (Trillion has no DB).

Three "tables":
  data/factory_tasks.json    — in-flight spawn tasks
  data/factory_agents.json   — registered config-driven agents
  data/factory_reports.json  — cached research reports (24h dedup)

The task store enforces the state machine on every transition and the daily cap
at creation time. A module lock guards concurrent access (heartbeat thread +
Flask request threads).
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from .models import State, can_transition, now_ts

_ROOT = Path(__file__).parent.parent.parent
_DATA = _ROOT / "data"
_lock = threading.RLock()

TASKS = _DATA / "factory_tasks.json"
AGENTS = _DATA / "factory_agents.json"
REPORTS = _DATA / "factory_reports.json"

RESERVED_SLUGS = frozenset({
    "trillion", "scheduler", "librarian", "scribe", "scout",
    "factory", "agent", "self", "system", "admin",
})
DAILY_CAP = 5
REPORT_TTL = 24 * 3600


def _load(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(path: Path, data: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Spawn tasks
# --------------------------------------------------------------------------- #

def count_today(requested_by: str = "user") -> int:
    cutoff = time.time() - 86400
    with _lock:
        return sum(1 for t in _load(TASKS)
                   if t.get("requested_by") == requested_by and t.get("created_at", 0) > cutoff)


def create_task(name_hint: str, role_description: str, special_requirements: str = "",
                requested_by: str = "user") -> dict:
    with _lock:
        if count_today(requested_by) >= DAILY_CAP:
            raise ValueError(f"daily factory cap reached ({DAILY_CAP}/day)")
        task = {
            "id": uuid.uuid4().hex[:16],
            "requested_by": requested_by,
            "name_hint": name_hint,
            "role_description": role_description,
            "special_requirements": special_requirements,
            "status": State.PENDING,
            "research_report_id": None,
            "proposed_manifest": None,
            "approval_iterations": 0,
            "revision_feedback": None,
            "error": None,
            "created_at": now_ts(),
        }
        tasks = _load(TASKS)
        tasks.append(task)
        _save(TASKS, tasks)
        return task


def get_task(task_id: str) -> dict | None:
    with _lock:
        return next((t for t in _load(TASKS) if t["id"] == task_id), None)


def update_task(task_id: str, **fields) -> dict:
    with _lock:
        tasks = _load(TASKS)
        for t in tasks:
            if t["id"] == task_id:
                t.update(fields)
                _save(TASKS, tasks)
                return t
        raise KeyError(task_id)


def transition(task_id: str, dst: str) -> dict:
    with _lock:
        t = get_task(task_id)
        if not t:
            raise KeyError(task_id)
        if not can_transition(t["status"], dst):
            raise ValueError(f"illegal transition {t['status']} -> {dst}")
        return update_task(task_id, status=dst)


def set_error(task_id: str, msg: str) -> None:
    with _lock:
        t = get_task(task_id)
        if t and can_transition(t["status"], State.FAILED):
            update_task(task_id, status=State.FAILED, error=msg[:500])


def list_pending() -> list:
    with _lock:
        return [t for t in _load(TASKS) if t["status"] == State.AWAITING_APPROVAL]


# --------------------------------------------------------------------------- #
# Agents
# --------------------------------------------------------------------------- #

def slug_taken(slug: str) -> bool:
    with _lock:
        return any(a["slug"] == slug for a in _load(AGENTS))


def save_agent(agent: dict) -> dict:
    with _lock:
        agents = _load(AGENTS)
        agents = [a for a in agents if a["slug"] != agent["slug"]]
        agents.append(agent)
        _save(AGENTS, agents)
        return agent


def list_active_agents() -> list:
    with _lock:
        return [a for a in _load(AGENTS) if a.get("status") == "active"]


def get_agent(slug: str) -> dict | None:
    with _lock:
        return next((a for a in _load(AGENTS) if a["slug"] == slug), None)


def archive_agent(slug: str) -> None:
    with _lock:
        agents = _load(AGENTS)
        for a in agents:
            if a["slug"] == slug:
                a["status"] = "archived"
        _save(AGENTS, agents)


# --------------------------------------------------------------------------- #
# Research reports (24h cache)
# --------------------------------------------------------------------------- #

def normalize_query(q: str) -> str:
    return " ".join((q or "").lower().split())


def cached_report(query: str) -> dict | None:
    key = normalize_query(query)
    with _lock:
        for r in _load(REPORTS):
            if r.get("query") == key and (now_ts() - r.get("created_at", 0)) < REPORT_TTL:
                return r
    return None


def save_report(query: str, report: dict) -> dict:
    with _lock:
        reports = _load(REPORTS)
        entry = {"id": uuid.uuid4().hex[:16], "query": normalize_query(query),
                 "report": report, "created_at": now_ts()}
        reports.append(entry)
        _save(REPORTS, reports[-100:])  # keep last 100
        return entry


def get_report(report_id: str) -> dict | None:
    with _lock:
        return next((r for r in _load(REPORTS) if r["id"] == report_id), None)
