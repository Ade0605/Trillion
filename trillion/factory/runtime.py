"""
Tier 5 — the config-driven runtime + hot-reload.

A spawned agent is PURE CONFIG: one ConfigDrivenAgent class reads a row and runs
a vanilla tool-use loop with that row's system_prompt, model, and tool allowlist.
No per-agent classes, no `if slug == ...` branches. Approving an agent registers
a `dispatch_to_<slug>` tool into the LIVE registry — dispatchable with no restart.
"""
from __future__ import annotations

from . import store
from ..provider import _get_client

_MAX_ITERS = 8


class ConfigDrivenAgent:
    def __init__(self, row: dict, registry, model: str | None = None):
        self._row = row
        self._registry = registry
        self._model = model or row.get("model") or "claude-sonnet-4-6"

    def _tools_for_api(self):
        allow = set(self._row.get("tool_allowlist") or [])
        return [t for t in self._registry.as_anthropic_tools() if t["name"] in allow]

    def run(self, user_message: str) -> str:
        client = _get_client()
        tools = self._tools_for_api()
        system = self._row.get("system_prompt") or "You are a helpful sub-agent."
        messages = [{"role": "user", "content": user_message}]
        text = ""
        for _ in range(_MAX_ITERS):
            kwargs = dict(model=self._model, max_tokens=2048, system=system, messages=messages)
            if tools:
                kwargs["tools"] = tools
            resp = client.messages.create(**kwargs)
            tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            if not tool_uses:
                return text or "(no response)"
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for tu in tool_uses:
                # spawned agents only see their allowlist (read-only) — skip the gate
                out = self._registry.run(tu.name, tu.input or {}, skip_confirm=True)
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": str(out)[:4000]})
            messages.append({"role": "user", "content": results})
        return text or "(reached iteration limit)"


def register_agent(registry, agent_row: dict) -> str:
    """Register (or refresh) the dispatch tool for one agent into a live registry."""
    slug = agent_row["slug"]
    name = f"dispatch_to_{slug}"

    def _dispatch(message: str) -> str:
        row = store.get_agent(slug) or agent_row
        return ConfigDrivenAgent(row, registry).run(message)

    registry.register(
        name,
        f"Dispatch a task to the '{agent_row.get('name', slug)}' sub-agent "
        f"({agent_row.get('specialty', '')}). Input: a natural-language message.",
        {"type": "object", "required": ["message"],
         "properties": {"message": {"type": "string"}}},
        _dispatch,
    )
    return name


def load_active_agents(registry) -> list[str]:
    """Register every active spawned agent — call once on host startup."""
    names = []
    for row in store.list_active_agents():
        try:
            names.append(register_agent(registry, row))
        except Exception:
            pass
    return names
