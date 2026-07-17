"""
Registers the Factory into Trillion's ToolRegistry:
  - `spawn_agent` (the meta-agent) — stages a spawn task and runs the pipeline in
    the background; the human approves at /factory. Confirmation-gated (research
    costs LLM tokens).
  - hot-reloads existing active agents as `dispatch_to_<slug>` tools on startup,
    and remembers the live registry so approval can register new ones with no
    restart.
"""
from __future__ import annotations

from . import store, live, pipeline
from .runtime import load_active_agents
from .sanitize import sanitize, UnsafeInputError

_SPAWN_SCHEMA = {
    "type": "object",
    "required": ["name_hint", "role_description"],
    "properties": {
        "name_hint": {"type": "string", "description": "short name for the new agent, e.g. 'doc summarizer'"},
        "role_description": {"type": "string", "description": "one paragraph: what the agent should do"},
        "special_requirements": {"type": "string", "description": "optional constraints/preferences"},
    },
}

_SPAWN_DESC = (
    "Mint a NEW specialist sub-agent. Researches the role, drafts a system prompt "
    "and tool allowlist, and stages it for the user's approval at /factory (it is "
    "NOT live until approved). Returns the task id."
)


def wire_live(registry) -> None:
    """Host-init step (call ONCE on the main registry): mark it live for
    hot-reload and register dispatch tools for already-approved agents.

    Kept OUT of register_factory_tools because build_registry() is also called
    incidentally (e.g. factory_allowed_names during research) — if that reset the
    live registry, approval would hot-register the dispatch tool into a throwaway
    registry and the new agent would never appear on the host's real registry.
    """
    live.set_registry(registry)
    load_active_agents(registry)


def register_factory_tools(registry) -> None:
    def spawn_agent(name_hint, role_description, special_requirements=""):
        try:
            role = sanitize(role_description)
        except UnsafeInputError as e:
            return f"Refused: {e}"
        if not role:
            return "Refused: empty role description."
        try:
            task = store.create_task(name_hint, role, sanitize(special_requirements))
        except ValueError as e:
            return f"Cannot spawn: {e}"
        pipeline.start_pipeline(task["id"])
        return (f"Staged spawn task {task['id']} for '{name_hint}'. Researching and "
                f"drafting the agent now — review and approve it at /factory when ready.")

    registry.register("spawn_agent", _SPAWN_DESC, _SPAWN_SCHEMA, spawn_agent,
                      requires_confirmation=True)
