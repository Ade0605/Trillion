"""
Mind-map skeleton: a flat, self-describing graph of Trillion's actual mind.

The single rule: never emit anything that isn't true. If a region has no data it
is empty and the stats say so; if a source errors it empties *that region only*
and records "error" in stats — never a 500, never a placeholder node, never an
invented edge.

This is a pure assembly function taking explicit sources, so it is testable
without a server. Each region is built inside its own try. Detail for one node
loads lazily from node_detail(); the skeleton never ships memory bodies.
"""
from __future__ import annotations

import datetime as _dt
import math
from pathlib import Path

REGION_COLORS = {
    "core": "#2DD4A8", "memory": "#A78BFA", "working": "#67E8F9",
    "agents": "#E88FB3", "knowledge": "#F5A524", "rim": "#8B93A1",
}
SIM_TOP_K = 3           # neighbours per memory in the similarity web
SIM_THRESHOLD = 0.35    # below this, two memories aren't "about the same thing"
MEMORY_CAP = 300        # cap node population; report the cap if hit


def _freshness(created: str | None) -> float:
    """Exponential decay on age, floored so nothing goes fully black."""
    if not created:
        return 0.6
    try:
        ts = _dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
        if ts.tzinfo:
            ts = ts.replace(tzinfo=None)
        age_days = max((_dt.datetime.now() - ts).total_seconds() / 86400.0, 0.0)
        return max(0.5 ** (age_days / 30.0), 0.15)
    except Exception:
        return 0.6


def _cos(a, b):
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(y * y for y in b))
    return s / (na * nb) if na and nb else 0.0


def build_skeleton(*, memory_store=None, session_store=None, registry=None,
                   factory_store=None, agent_name="Trillion",
                   knowledge_files=None, embed_fn=None) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    stats: dict = {}
    regions = [{"id": r, "color": c} for r, c in REGION_COLORS.items()]

    # ---- core: the agent + its two prompt blocks ------------------------- #
    nodes.append({"id": "core:agent", "type": "agent", "region": "core",
                  "label": agent_name, "color": REGION_COLORS["core"],
                  "size": 3.0, "freshness": 1.0, "extra": {"kind": "self"}})
    for block in ("stable", "dynamic"):
        nodes.append({"id": f"core:prompt-{block}", "type": "prompt", "region": "core",
                      "label": f"{block} prompt", "color": REGION_COLORS["core"],
                      "size": 1.0, "freshness": 0.8, "extra": {"block": block}})

    # ---- memory: the semantic web ---------------------------------------- #
    mems = []
    try:
        if memory_store is not None:
            mems = memory_store.all()[:MEMORY_CAP]
        stats["memory_total"] = memory_store.count() if memory_store else 0
        stats["memory_shown"] = len(mems)
        if memory_store and memory_store.count() > MEMORY_CAP:
            stats["memory_capped_at"] = MEMORY_CAP
        for m in mems:
            nodes.append({"id": f"mem:{m.slug}", "type": "memory", "region": "memory",
                          "label": m.hook, "color": REGION_COLORS["memory"],
                          "size": 1.0, "freshness": _freshness(m.created),
                          "extra": {"mtype": m.type}})
    except Exception:
        stats["memory"] = "error"
        mems = []

    # similarity edges + degree-scaled size + core-ward recall trunks
    try:
        if len(mems) >= 2 and embed_fn is not None:
            vecs = embed_fn([m.hook + "\n" + m.body for m in mems])
            if vecs and len(vecs) == len(mems):
                stats["memory_edges"] = "semantic"
                degree = {m.slug: 0 for m in mems}
                seen = set()
                for i, mi in enumerate(mems):
                    sims = sorted(
                        ((j, _cos(vecs[i], vecs[j])) for j in range(len(mems)) if j != i),
                        key=lambda t: t[1], reverse=True)[:SIM_TOP_K]
                    for j, s in sims:
                        if s < SIM_THRESHOLD:
                            continue
                        a, b = sorted((mi.slug, mems[j].slug))
                        key = (a, b)
                        if key in seen:
                            continue
                        seen.add(key)
                        edges.append({"source": f"mem:{a}", "target": f"mem:{b}",
                                      "kind": "similarity", "weight": round(s, 3)})
                        degree[a] += 1; degree[b] += 1
                for n in nodes:
                    if n["type"] == "memory":
                        d = degree.get(n["id"].split(":", 1)[1], 0)
                        n["size"] = 1.0 + min(d, 6) * 0.25
                # recall trunks: highest-degree (or freshest) memories hang off core
                ranked = sorted(mems, key=lambda m: (degree.get(m.slug, 0),
                                                      _freshness(m.created)), reverse=True)
                trunks = ranked[:3]
            else:
                stats["memory_edges"] = "none (embeddings unavailable)"
                trunks = sorted(mems, key=lambda m: _freshness(m.created), reverse=True)[:3]
        else:
            if mems:
                stats["memory_edges"] = "none (too few to wire)" if len(mems) < 2 \
                    else "none (no embed fn)"
            trunks = sorted(mems, key=lambda m: _freshness(m.created), reverse=True)[:3]
        for m in trunks:                      # recall always flows core-ward
            edges.append({"source": f"mem:{m.slug}", "target": "core:agent",
                          "kind": "recall", "weight": 1.0})
    except Exception:
        stats["memory_edges"] = "error"

    # ---- working: recent conversation threads ---------------------------- #
    try:
        recent = session_store.list_recent(8) if session_store else []
        stats["working_shown"] = len(recent)
        for s in recent:
            nodes.append({"id": f"thread:{s['id']}", "type": "thread", "region": "working",
                          "label": "session " + s["id"][:6], "color": REGION_COLORS["working"],
                          "size": 1.0, "freshness": _freshness(
                              _dt.datetime.fromtimestamp(s["modified"]).isoformat()),
                          "extra": {}})
            edges.append({"source": f"thread:{s['id']}", "target": "core:agent",
                          "kind": "working", "weight": 0.5})
    except Exception:
        stats["working"] = "error"

    # ---- agents: sub-agents, tools as moons ------------------------------ #
    try:
        active = factory_store.list_active_agents() if factory_store else []
        stats["agents_shown"] = len(active)
        for a in active:
            slug = a.get("slug", "")
            if not slug:
                continue
            aid = f"agent:{slug}"
            nodes.append({"id": aid, "type": "subagent", "region": "agents",
                          "label": a.get("name") or slug, "color": REGION_COLORS["agents"],
                          "size": 1.8, "freshness": 0.9,
                          "extra": {"specialty": a.get("specialty", "")}})
            edges.append({"source": "core:agent", "target": aid,
                          "kind": "dispatch", "weight": 1.0})
            for t in (a.get("tool_allowlist") or [])[:8]:
                mid = f"agent:{slug}:tool:{t}"
                nodes.append({"id": mid, "type": "agent-tool", "region": "agents",
                              "label": t, "color": REGION_COLORS["agents"],
                              "size": 0.6, "freshness": 0.7, "extra": {}})
                edges.append({"source": aid, "target": mid, "kind": "has-tool", "weight": 0.4})
    except Exception:
        stats["agents"] = "error"

    # ---- knowledge: always-loaded files ---------------------------------- #
    try:
        files = knowledge_files or []
        stats["knowledge_shown"] = len(files)
        for f in files:
            p = Path(f)
            fresh = _freshness(_dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat()) \
                if p.exists() else 0.6
            kid = f"know:{f}"
            nodes.append({"id": kid, "type": "knowledge", "region": "knowledge",
                          "label": p.name, "color": REGION_COLORS["knowledge"],
                          "size": 1.0, "freshness": fresh, "extra": {"path": f}})
            edges.append({"source": kid, "target": "core:prompt-stable",
                          "kind": "loads", "weight": 0.6})
    except Exception:
        stats["knowledge"] = "error"

    # ---- rim: the tool inventory ----------------------------------------- #
    try:
        tools = list(registry._tools.values()) if registry else []
        stats["rim_shown"] = len(tools)
        for t in tools:
            tid = f"tool:{t.name}"
            cat = t.name.split("_", 1)[0]
            nodes.append({"id": tid, "type": "tool", "region": "rim",
                          "label": t.name, "color": REGION_COLORS["rim"],
                          "size": 0.8, "freshness": 0.7,
                          "extra": {"category": cat,
                                    "gated": bool(getattr(t, "requires_confirmation", False))}})
            edges.append({"source": "core:agent", "target": tid, "kind": "capability", "weight": 0.3})
    except Exception:
        stats["rim"] = "error"

    stats["nodes"] = len(nodes)
    stats["edges"] = len(edges)
    return {"regions": regions, "nodes": nodes, "edges": edges, "stats": stats}


def node_detail(node_id: str, *, memory_store=None, factory_store=None,
                knowledge_files=None) -> dict | None:
    """Full detail for one node. Knowledge previews are restricted to the
    manifest — never an arbitrary path (that would be directory traversal)."""
    prefix, _, rest = node_id.partition(":")
    if prefix == "mem" and memory_store is not None:
        m = memory_store.get(rest)
        if not m:
            return None
        return {"id": node_id, "type": "memory", "label": m.hook, "body": m.body,
                "mtype": m.type, "source": m.source, "created": m.created}
    if prefix == "agent" and factory_store is not None and ":tool:" not in node_id:
        a = next((x for x in factory_store.list_active_agents() if x.get("slug") == rest), None)
        if not a:
            return None
        return {"id": node_id, "type": "subagent", "label": a.get("name") or rest,
                "specialty": a.get("specialty", ""), "model": a.get("model", ""),
                "tools": a.get("tool_allowlist", [])}
    if prefix == "know":
        allowed = set(knowledge_files or [])
        if rest not in allowed:                # manifest-only: no arbitrary paths
            return None
        p = Path(rest)
        preview = ""
        try:
            preview = p.read_text(encoding="utf-8")[:2000]
        except Exception:
            preview = "(unreadable)"
        return {"id": node_id, "type": "knowledge", "label": p.name, "preview": preview}
    return {"id": node_id, "type": prefix}     # core/tool/thread: id echo, nothing private
