"""
Tier 4 — the human approval gate.

approve  → insert a spawned_agents row, flip task APPROVED, hot-register the
           dispatch tool, emit `agent_added` (carrying created_by_task_id so the
           approval surface can clear the right row).
reject   → with feedback: roll back to WRITING_PROMPT, regenerate ONLY the system
           prompt (research/spec already cached), return to AWAITING_APPROVAL,
           until the iteration cap; without feedback: terminal REJECTED.
"""
from __future__ import annotations

import uuid
from typing import Callable

from . import store, prompts, live, runtime
from .models import State, now_ts

MAX_ITERATIONS = 3


def _emit(cb, kind, **event):
    if cb:
        try:
            cb({"kind": kind, **event})
        except Exception:
            pass


def handle_approve(task_id: str, on_event: Callable | None = None) -> dict:
    task = store.get_task(task_id)
    if not task or task["status"] != State.AWAITING_APPROVAL:
        raise ValueError("task not in approvable state")
    p = task["proposed_manifest"] or {}
    slug = p["slug"]
    if slug in store.RESERVED_SLUGS or store.slug_taken(slug):
        raise ValueError(f"slug '{slug}' unavailable at approval time")

    agent = {
        "id": uuid.uuid4().hex[:16],
        "slug": slug, "name": p["name"], "specialty": p.get("specialty", ""),
        "system_prompt": p["system_prompt"], "tool_allowlist": p.get("tool_allowlist", []),
        "model": p.get("model", "claude-sonnet-4-6"),
        "status": "active", "created_by_task_id": task_id, "created_at": now_ts(),
    }
    store.save_agent(agent)
    store.transition(task_id, State.APPROVED)

    reg = live.get_registry()
    tool_name = None
    if reg is not None:
        tool_name = runtime.register_agent(reg, agent)  # hot-reload, no restart

    _emit(on_event, "agent_added", slug=slug, name=agent["name"],
          created_by_task_id=task_id, tool=tool_name)
    return {"status": "approved", "slug": slug, "tool": tool_name}


def handle_reject(task_id: str, feedback: str = "", on_event: Callable | None = None) -> dict:
    task = store.get_task(task_id)
    if not task or task["status"] != State.AWAITING_APPROVAL:
        raise ValueError("task not in rejectable state")

    if not (feedback or "").strip():
        store.transition(task_id, State.REJECTED)
        _emit(on_event, "rejected", task_id=task_id)
        return {"status": "rejected"}

    iters = task.get("approval_iterations", 0) + 1
    if iters >= MAX_ITERATIONS:
        store.update_task(task_id, revision_feedback=feedback, approval_iterations=iters)
        store.set_error(task_id, f"revision cap ({MAX_ITERATIONS}) reached")
        _emit(on_event, "failed", task_id=task_id, error="revision cap reached")
        return {"status": "failed", "reason": "revision cap reached"}

    # regenerate ONLY the system prompt (research + spec already cached)
    store.update_task(task_id, revision_feedback=feedback, approval_iterations=iters)
    store.transition(task_id, State.WRITING_PROMPT)
    p = task["proposed_manifest"] or {}
    report_entry = store.get_report(task.get("research_report_id") or "")
    report = report_entry["report"] if report_entry else {"competencies": [], "tools_available": p.get("tool_allowlist", [])}
    new_prompt = prompts.generate_system_prompt(
        p["name"], task["role_description"], report, task.get("special_requirements", ""),
        prior_prompt=p.get("system_prompt"), revision_feedback=feedback)
    p["system_prompt"] = new_prompt
    store.update_task(task_id, proposed_manifest=p)
    store.transition(task_id, State.AWAITING_APPROVAL)
    _emit(on_event, "awaiting_approval", task_id=task_id, slug=p["slug"], name=p["name"], manifest=p)
    return {"status": "awaiting_approval", "iteration": iters}
