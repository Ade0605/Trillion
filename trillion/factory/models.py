"""
Factory data models + the spawn-pipeline state machine.

No Pydantic (matching Trillion's conventions) — lightweight dataclasses with a
manual validator for the one payload that comes from an LLM (the Skills Report).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict


class State:
    PENDING = "pending"
    RESEARCHING = "researching"
    DRAFTING_SPEC = "drafting_spec"
    WRITING_PROMPT = "writing_prompt"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


# Invalid transitions fail loudly at the store layer, never silently.
_TRANSITIONS = {
    State.PENDING:           {State.RESEARCHING, State.FAILED},
    State.RESEARCHING:       {State.DRAFTING_SPEC, State.FAILED},
    State.DRAFTING_SPEC:     {State.WRITING_PROMPT, State.FAILED},
    State.WRITING_PROMPT:    {State.AWAITING_APPROVAL, State.FAILED},
    State.AWAITING_APPROVAL: {State.APPROVED, State.REJECTED, State.WRITING_PROMPT, State.FAILED},
    State.APPROVED:          set(),
    State.REJECTED:          set(),
    State.FAILED:            set(),
}


def can_transition(src: str, dst: str) -> bool:
    return dst in _TRANSITIONS.get(src, set())


@dataclass
class Source:
    url: str
    title: str
    excerpt: str = ""


@dataclass
class ToolWishlistEntry:
    name: str
    purpose: str
    external_dependency: str = ""


@dataclass
class SkillsReport:
    domain: str
    competencies: list = field(default_factory=list)
    tools_available: list = field(default_factory=list)
    tools_wishlist: list = field(default_factory=list)   # list[ToolWishlistEntry|dict]
    design_patterns: list = field(default_factory=list)
    sources: list = field(default_factory=list)          # list[Source|dict]

    def to_dict(self) -> dict:
        return asdict(self)


def validate_skills_report(payload: dict) -> SkillsReport:
    """Coerce + validate the LLM-emitted report. Raises ValueError on bad shape."""
    if not isinstance(payload, dict):
        raise ValueError("skills report is not an object")
    domain = str(payload.get("domain") or "").strip()
    if not domain:
        raise ValueError("skills report missing domain")
    comps = [str(c).strip() for c in (payload.get("competencies") or []) if str(c).strip()]
    if not comps:
        raise ValueError("skills report has no competencies")
    avail = [str(t).strip() for t in (payload.get("tools_available") or []) if str(t).strip()]
    wish = []
    for w in payload.get("tools_wishlist") or []:
        if isinstance(w, dict) and w.get("name"):
            wish.append({"name": str(w["name"]), "purpose": str(w.get("purpose", "")),
                         "external_dependency": str(w.get("external_dependency", ""))})
    patterns = [str(p).strip() for p in (payload.get("design_patterns") or []) if str(p).strip()]
    sources = []
    for s in payload.get("sources") or []:
        if isinstance(s, dict) and s.get("url"):
            sources.append({"url": str(s["url"]), "title": str(s.get("title", "")),
                            "excerpt": str(s.get("excerpt", ""))[:400]})
    return SkillsReport(domain=domain, competencies=comps[:8], tools_available=avail,
                        tools_wishlist=wish, design_patterns=patterns[:5], sources=sources[:15])


def now_ts() -> float:
    return time.time()
