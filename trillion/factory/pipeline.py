"""
Tier 3 — the spawn pipeline. Walks a task from PENDING to AWAITING_APPROVAL,
one DB (JSON) update per transition. Any exception lands the task in FAILED —
a started task always ends in a terminal state.

Trillion is sync/Flask, so the pipeline runs in a daemon thread. We keep a strong
reference to it in a module-level set (the thread analogue of the asyncio
weak-reference footgun) so it can't be dropped mid-run.
"""
from __future__ import annotations

import threading
from typing import Callable

from . import store, research, prompts
from .models import State
from .research import factory_allowed_names

_IN_FLIGHT: set[threading.Thread] = set()
DEFAULT_MODEL = "claude-sonnet-4-6"


def _emit(cb, kind, **event):
    if cb:
        try:
            cb({"kind": kind, **event})
        except Exception:
            pass


def run(task_id: str, on_event: Callable | None = None) -> None:
    task = store.get_task(task_id)
    if not task:
        return
    try:
        # slug pick + reserved/collision guard BEFORE any LLM work
        slug = prompts.slugify(task["name_hint"])
        if slug in store.RESERVED_SLUGS:
            raise ValueError(f"slug '{slug}' is reserved")
        if store.slug_taken(slug):
            raise ValueError(f"slug '{slug}' already exists")

        # research
        store.transition(task_id, State.RESEARCHING)
        _emit(on_event, "state", task_id=task_id, status=State.RESEARCHING)
        report, report_id, cached = research.research(task["role_description"])
        store.update_task(task_id, research_report_id=report_id)

        # spec markdown
        store.transition(task_id, State.DRAFTING_SPEC)
        _emit(on_event, "state", task_id=task_id, status=State.DRAFTING_SPEC)
        name = task["name_hint"].replace("-", " ").title()
        prompts.write_spec_markdown(slug, name, report,
                                    task["role_description"], task.get("special_requirements", ""))

        # system prompt
        store.transition(task_id, State.WRITING_PROMPT)
        _emit(on_event, "state", task_id=task_id, status=State.WRITING_PROMPT)
        system_prompt = prompts.generate_system_prompt(
            name, task["role_description"], report, task.get("special_requirements", ""))

        # tool allowlist = report picks ∩ actually-allowed
        allowed = set(factory_allowed_names())
        tool_allowlist = [t for t in report.get("tools_available", []) if t in allowed]

        manifest = {
            "slug": slug, "name": name,
            "specialty": report.get("domain") or (report.get("competencies") or ["general"])[0],
            "system_prompt": system_prompt,
            "tool_allowlist": tool_allowlist,
            "model": DEFAULT_MODEL,
            "tools_wishlist": report.get("tools_wishlist", []),
        }
        store.update_task(task_id, proposed_manifest=manifest)

        store.transition(task_id, State.AWAITING_APPROVAL)
        _emit(on_event, "awaiting_approval", task_id=task_id, slug=slug, name=name,
              manifest=manifest)
    except Exception as exc:
        store.set_error(task_id, str(exc))
        _emit(on_event, "failed", task_id=task_id, error=str(exc))


def start_pipeline(task_id: str, on_event: Callable | None = None) -> threading.Thread:
    """Run the pipeline in a tracked daemon thread (strong reference held)."""
    t = threading.Thread(target=_run_tracked, args=(task_id, on_event), daemon=True)
    _IN_FLIGHT.add(t)
    t.start()
    return t


def _run_tracked(task_id, on_event):
    try:
        run(task_id, on_event)
    finally:
        _IN_FLIGHT.discard(threading.current_thread())
