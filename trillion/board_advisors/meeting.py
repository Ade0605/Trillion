"""
meeting — the fan-out. For each selected seat, ONE model call whose system
prompt contains that seat's dossier and nothing else; it does not know who else
is in the room. Isolation is the structural defence against consensus theatre:
never one call playing several parts.

Every field the model returns is treated as hostile input — a boolean may come
back as the string "false" (truthy), citations may be fabricated, a sentence may
arrive where a list belonged. Coerce by value, gate the citations, drop the rest.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .gate import gate_citations, is_unsourced

SEAT_MAX_TOKENS = 1000          # generous: a truncated seat is a wasted call


@dataclass
class SeatOpinion:
    seat_id: str
    name: str
    position: str = ""
    reasoning: str = ""
    citations: list[str] = field(default_factory=list)   # gated
    confidence: float = 0.0
    change_mind: str = ""
    abstained: bool = False
    unsourced: bool = False
    error: str = ""


def render_dossier(seat) -> str:
    lines = [f"You are {seat.name}, a member of a board of advisors. Your seat: "
             f"{seat.seat}.",
             "Argue ONLY from your own doctrine below, in your own voice, and cite "
             "the doctrine ids (D1, D2…) you actually use. If none of your doctrine "
             "genuinely applies, ABSTAIN — that is a real and valued answer; never "
             "invent a position to seem useful. Push back wherever your "
             "characteristic objection applies.",
             "\n## Your doctrine"]
    for d in seat.doctrine:
        if d.verification == "retired":
            continue
        lines.append(f"{d.id} — {d.title}  [{d.source}]\n{d.body}")
    lines += [f"\n## You characteristically object to\n{seat.objection}",
              f"\n## Your blind spots (be honest — the chair will discount you here)\n{seat.blind_spots}",
              f"\n## Your voice\n{seat.voice}",
              '\nReturn ONLY JSON: {"position": string, "reasoning": string, '
              '"citations": [doctrine ids], "confidence": 0..1, "change_mind": '
              'string, "abstain": boolean}.']
    return "\n".join(lines)


def _coerce_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "yes", "1")


def _coerce_float(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))


def _coerce_str(v) -> str:
    return v.strip() if isinstance(v, str) else ("" if v is None else str(v))


def parse_opinion(raw: str, seat) -> SeatOpinion:
    try:
        m = re.search(r"\{.*\}", raw or "", re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
    except Exception:
        data = {}
    cites_in = data.get("citations")
    cites_in = cites_in if isinstance(cites_in, list) else []
    citations = gate_citations(cites_in, seat.shown_ids())      # strip fabricated/withheld
    abstained = _coerce_bool(data.get("abstain"))
    return SeatOpinion(
        seat_id=seat.id, name=seat.name,
        position=_coerce_str(data.get("position")),
        reasoning=_coerce_str(data.get("reasoning")),
        citations=citations,
        confidence=_coerce_float(data.get("confidence")),
        change_mind=_coerce_str(data.get("change_mind")),
        abstained=abstained,
        unsourced=is_unsourced(citations, abstained),
    )


def ask_seat(seat, question, brief, *, complete_fn, max_tokens=SEAT_MAX_TOKENS) -> SeatOpinion:
    system = render_dossier(seat)
    prompt = f"The business brief:\n{brief}\n\nThe question for the board:\n{question}"
    raw = complete_fn(prompt, system=system, max_tokens=max_tokens)
    return parse_opinion(raw, seat)


def hold_meeting(question, seat_ids, roster, brief, *, complete_fn,
                 cost_ceiling=None, cost_of=None, max_tokens=SEAT_MAX_TOKENS):
    """Fan out to each distinct seat. Returns (opinions, spent).

    `cost_ceiling`: stop before a call would exceed it — a ceiling of 0 spends
    nothing (the check is BEFORE the call, so "spend nothing" really does).
    `cost_of(seat_id, raw)`: real cost of a returned call; default estimates from
    length. A seat that errors or times out loses only its own voice.
    """
    seen, distinct = set(), []
    for sid in seat_ids:                       # de-dup: never buy two calls to one dossier
        if sid in roster and sid not in seen:
            seen.add(sid)
            distinct.append(sid)

    cost_of = cost_of or (lambda sid, raw: 0.000001 * len(raw or ""))
    opinions: list[SeatOpinion] = []
    spent = 0.0
    for sid in distinct:
        if cost_ceiling is not None and spent >= cost_ceiling:   # 0 >= 0 → no calls at all
            break
        seat = roster[sid]
        try:
            raw = complete_fn(
                f"The business brief:\n{brief}\n\nThe question for the board:\n{question}",
                system=render_dossier(seat), max_tokens=max_tokens)
            opinions.append(parse_opinion(raw, seat))
            spent += cost_of(sid, raw)
        except Exception as e:                 # a seat may fail without failing the meeting
            opinions.append(SeatOpinion(seat_id=sid, name=seat.name, error=str(e)[:120]))
    return opinions, spent
