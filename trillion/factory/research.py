"""
Tier 1 — research subagent. Given a role/domain, produce a schema-validated
Skills Report (competencies, available tools, wishlist, sources). Uses a real
Anthropic tool-use loop with web_search + a forced emit_skills_report on the
last iteration, and a 24h cache.
"""
from __future__ import annotations

from . import store
from .models import validate_skills_report
from ..provider import _get_client

# Read-only tools a spawned agent may safely be handed. Mutating/gated tools are
# excluded — anything an agent wants beyond this shows up as a wishlist item.
_FACTORY_DENY = {
    "add_reminder", "complete_reminder", "delete_reminder", "draft_message",
    "remember_fact", "update_memory", "forget_fact", "web_search", "design_screen",
}


def factory_allowed_names() -> list[str]:
    """Names from the live registry a spawned agent may use (read-only, ungated)."""
    try:
        from ..tools.registry import build_registry
        from ..memory import MemoryStore, register_memory_tools
        r = build_registry()
        register_memory_tools(r, MemoryStore())
        return sorted(
            t.name for t in r._tools.values()
            if not getattr(t, "requires_confirmation", False) and t.name not in _FACTORY_DENY
        )
    except Exception:
        return []


_web_fn = None


def _run_web_search(query: str) -> str:
    global _web_fn
    if _web_fn is None:
        try:
            from ..tools.registry import build_registry
            t = build_registry()._tools.get("web_search")
            _web_fn = t.fn if t else (lambda **k: "web_search unavailable")
        except Exception:
            _web_fn = lambda **k: "web_search unavailable"
    try:
        return str(_web_fn(query=query))
    except Exception as e:
        return f"[search error] {e}"


_WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": "Search the web for evidence about the domain.",
    "input_schema": {"type": "object", "required": ["query"],
                     "properties": {"query": {"type": "string"}}},
}

_EMIT_TOOL = {
    "name": "emit_skills_report",
    "description": "Emit the final structured Skills Report. Call this exactly once at the end.",
    "input_schema": {
        "type": "object",
        "required": ["domain", "competencies", "tools_available"],
        "properties": {
            "domain": {"type": "string"},
            "competencies": {"type": "array", "items": {"type": "string"}},
            "tools_available": {"type": "array", "items": {"type": "string"}},
            "tools_wishlist": {"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"}, "purpose": {"type": "string"},
                "external_dependency": {"type": "string"}}}},
            "design_patterns": {"type": "array", "items": {"type": "string"}},
            "sources": {"type": "array", "items": {"type": "object", "properties": {
                "url": {"type": "string"}, "title": {"type": "string"},
                "excerpt": {"type": "string"}}}},
        },
    },
}

_SYSTEM = """You are a research specialist. Research what an agent that does <{domain}>
should be capable of, and produce a structured Skills Report.

Use web_search 3-6 times to gather real evidence from real sources (vendor docs,
open-source projects, technical blogs).

You MUST end by calling emit_skills_report with:
- domain: the domain you researched
- competencies: 4-8 concrete capabilities the agent should have
- tools_available: tool names from THIS catalog the agent can use today:
{catalog}
- tools_wishlist: tools we DON'T have yet that this agent would need (name/purpose/external_dependency)
- design_patterns: 2-5 real patterns you observed
- sources: 5-15 sources with url + title + short excerpt (<400 chars)

Quote excerpts must be SHORT and clearly attributable."""


def research(domain: str, model: str = "claude-sonnet-4-6", max_iterations: int = 8) -> tuple[dict, str, bool]:
    """Return (report_dict, report_id, cache_hit)."""
    cached = store.cached_report(domain)
    if cached:
        return cached["report"], cached["id"], True

    catalog = "\n".join(f"  - {n}" for n in factory_allowed_names()) or "  (none)"
    system = _SYSTEM.format(domain=domain, catalog=catalog)
    client = _get_client()
    messages = [{"role": "user",
                 "content": f"Research what an agent that does '{domain}' should be capable of."}]
    report = None

    for i in range(max_iterations):
        kwargs = dict(model=model, max_tokens=2048, system=system, messages=messages,
                      tools=[_WEB_SEARCH_TOOL, _EMIT_TOOL])
        if i == max_iterations - 1:   # force the emit on the last turn
            kwargs["tool_choice"] = {"type": "tool", "name": "emit_skills_report"}
        resp = client.messages.create(**kwargs)

        tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        messages.append({"role": "assistant", "content": resp.content})
        if not tool_uses:
            messages.append({"role": "user", "content": "Keep researching, then emit the report."})
            continue

        results = []
        for tu in tool_uses:
            if tu.name == "web_search":
                out = _run_web_search((tu.input or {}).get("query", ""))
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out[:4000]})
            elif tu.name == "emit_skills_report":
                report = tu.input
        if report is not None:
            break
        messages.append({"role": "user", "content": results})

    if report is None:
        raise RuntimeError("research loop finished without emitting a report")
    validated = validate_skills_report(report).to_dict()
    entry = store.save_report(domain, validated)
    return validated, entry["id"], False
