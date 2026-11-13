"""
routing — one cheap call (plus deterministic name matching) decides two things
before any fan-out: is this a board question at all, and which seats have
standing. Getting the DECLINE gate wrong is actively bad — erring toward
"decline" refuses exactly the questions a board exists for — so the criteria are
concrete and business-decisions-about-your-own-company are stated as the core
use case, never declined as "personal".
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

MAX_SEATS = 4


@dataclass
class RouteResult:
    is_board_question: bool
    seat_ids: list[str] = field(default_factory=list)
    decline_reason: str = ""
    named: list[str] = field(default_factory=list)   # seats the user asked for by name


def normalize(text: str) -> str:
    """Fold the unicode a dictated or pasted question arrives with, so name
    matching doesn't fail silently: curly/ fullwidth apostrophes, nbsp, soft
    hyphen, compatibility forms."""
    s = unicodedata.normalize("NFKC", text or "")
    for ch in ("’", "ʼ", "‘", "＇", "`"):
        s = s.replace(ch, "'")
    s = s.replace(" ", " ").replace("­", "")
    return s


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[\s'’.-]+", name.lower()) if t]


def match_names(question: str, roster, user_names=()) -> list[str]:
    """Seats the user named explicitly. Matches on a distinctive name token
    (>=4 chars), but NEVER on a token that is one of the user's own names — a
    bare first name that collides with the user is ambiguous and must not route.
    """
    q = normalize(question).lower()
    users = {normalize(u).lower() for u in user_names}
    hit: list[str] = []
    for sid, seat in roster.items():
        toks = [t for t in (_tokens(seat.name) + [sid]) if len(t) >= 4 and t not in users]
        if any(re.search(rf"\b{re.escape(t)}\b", q) for t in toks):
            hit.append(sid)
    return hit


def _seats_doc(roster) -> str:
    return "\n".join(f"- {sid}: {s.seat} — domains: {', '.join(s.domains)}"
                     for sid, s in roster.items())


def build_router_prompt(question: str, roster) -> tuple[str, str]:
    system = (
        "You route a question to a board of business advisors. Return ONLY JSON: "
        '{"decline": bool, "decline_reason": string, "seats": [seat_id, ...]}.\n\n'
        "DECLINE (decline=true) ONLY if the question is: software/technical code, "
        "medical or health, legal advice, or a family/personal-relationship "
        "matter. A business decision about the user's OWN company is the CORE use "
        "case of this board — NEVER decline it as 'personal', however personal it "
        "feels (e.g. 'should I cut this product/service', 'should I fire a client', "
        "'should I raise prices' are all board questions).\n\n"
        "Otherwise decline=false and pick the seats whose domains give them "
        "standing. Pick only seats that genuinely fit; fewer good seats beat many "
        "weak ones. Seats:\n" + _seats_doc(roster))
    return system, f"Question: {question}"


def _coerce_bool(v) -> bool:
    """A JSON boolean may come back as the string 'false' (truthy in most langs).
    Check the value, not its truthiness."""
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "yes", "1")


def parse_router(raw: str, roster) -> tuple[bool, str, list[str]]:
    """Parse the router's JSON defensively. Unknown seat ids are dropped."""
    try:
        m = re.search(r"\{.*\}", raw or "", re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
    except Exception:
        data = {}
    decline = _coerce_bool(data.get("decline"))
    reason = str(data.get("decline_reason") or "").strip()
    seats = data.get("seats") or []
    if not isinstance(seats, list):
        seats = []
    ids = [str(s).strip().lower() for s in seats]
    ids = [i for i in ids if i in roster]
    return decline, reason, ids


def route(question: str, roster, *, complete_fn, user_names=()) -> RouteResult:
    """Decide standing. `complete_fn(prompt, system=...)` is the cheap model call;
    inject it for tests. Named seats are forced in (the user asked for them)."""
    named = match_names(question, roster, user_names)

    system, prompt = build_router_prompt(question, roster)
    try:
        raw = complete_fn(prompt, system=system)
    except Exception:
        raw = ""
    decline, reason, router_ids = parse_router(raw, roster)

    # If the user named advisors, it IS a board question and they are seated,
    # regardless of the router's decline (an explicit ask overrides the gate).
    if named:
        seat_ids = named + [i for i in router_ids if i not in named]
        return RouteResult(True, seat_ids[:MAX_SEATS], "", named)

    if decline:
        return RouteResult(False, [], reason or "Not a question for the board.", [])

    if not router_ids:
        return RouteResult(False, [], "No advisor has standing on this.", [])

    return RouteResult(True, router_ids[:MAX_SEATS], "", [])
