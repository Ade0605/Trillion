"""
chair — Trillion synthesizes. The seats are well-read but blind; the chair is the
only participant that has read the live business brief. It names the split before
the agreement, discounts seats by their documented blind spots, treats
abstention as abstention, and flags positions resting on unverified doctrine as
the user's own assumption rather than the advisor's documented view.

Two guards are DETERMINISTIC, never trusted to the prompt:
  1. Fewer than two non-abstaining seats can never be reported as unanimous.
  2. The spoken line must match the computed verdict — if the guard says "not
     unanimous", the sentence read aloud may not say "unanimous".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

CHAIR_MAX_TOKENS = 1400          # larger than a seat's — it consumes them all

_UNANIMOUS = re.compile(r"\b(unanimous(?:ly)?|all (?:agree|agreed)|everyone agrees|"
                        r"the board agrees|consensus)\b", re.I)


@dataclass
class ChairVerdict:
    spoken: str                                  # 1-2 sentences, leads with the split
    detail: str = ""                             # the longer written synthesis
    unanimous: bool = False
    speakers: int = 0                            # non-abstaining, non-errored seats
    abstained: list[str] = field(default_factory=list)
    guard_fired: bool = False                    # did a deterministic guard correct the prose


def _opinions_block(opinions, roster) -> str:
    out = []
    for o in opinions:
        if o.error:
            out.append(f"- {o.name}: (no answer — {o.error})")
            continue
        if o.abstained:
            out.append(f"- {o.name}: ABSTAINED (no doctrine applies — this is NOT agreement).")
            continue
        seat = roster.get(o.seat_id)
        blind = (seat.blind_spots if seat else "").strip()
        flag = " [rests on an entry you wrote yourself, not documented doctrine]" if o.unsourced else ""
        out.append(
            f"- {o.name} (confidence {o.confidence:.2f}, cites {', '.join(o.citations) or 'none'}{flag}):\n"
            f"    position: {o.position}\n"
            f"    reasoning: {o.reasoning}\n"
            f"    would change its mind if: {o.change_mind}\n"
            f"    this seat's blind spots: {blind}")
    return "\n".join(out)


def build_chair_prompt(question, opinions, brief, roster) -> tuple[str, str]:
    system = (
        "You chair a board of advisors and you are the only one who has read the "
        "live business brief. Synthesize the seats' opinions. Rules: name the "
        "SPLIT before any agreement (where they divided is the information; where "
        "they agreed is often just the obvious); discount a seat when its position "
        "falls inside its own documented blind spots, and say so; treat an "
        "abstention as an abstention, never as assent; flag any position marked as "
        "resting on an entry the user wrote as the user's own assumption, not the "
        "advisor's documented view. Return ONLY JSON: "
        '{"spoken": "1-2 sentences, lead with the split", "detail": "the fuller '
        'written synthesis", "unanimous": boolean}.')
    user = (f"Business brief (live):\n{brief}\n\nThe question:\n{question}\n\n"
            f"The board said:\n{_opinions_block(opinions, roster)}")
    return system, user


def _coerce_bool(v) -> bool:
    return v if isinstance(v, bool) else str(v).strip().lower() in ("true", "yes", "1")


def synthesize(question, opinions, brief, roster, *, complete_fn,
               max_tokens=CHAIR_MAX_TOKENS) -> ChairVerdict:
    speakers = [o for o in opinions if not o.abstained and not o.error]
    abstained = [o.name for o in opinions if o.abstained]

    system, user = build_chair_prompt(question, opinions, brief, roster)
    try:
        raw = complete_fn(user, system=system, max_tokens=max_tokens)
        m = re.search(r"\{.*\}", raw or "", re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
    except Exception:
        data = {}

    spoken = (data.get("spoken") or "").strip()
    detail = (data.get("detail") or "").strip()
    claimed = _coerce_bool(data.get("unanimous"))

    # Guard 1: unanimity needs at least two non-abstaining voices.
    unanimous = claimed and len(speakers) >= 2

    # Guard 2: the spoken line must match the computed verdict.
    guard_fired = False
    if not unanimous and spoken and _UNANIMOUS.search(spoken):
        spoken = _UNANIMOUS.sub("divided", spoken)
        guard_fired = True
    if not spoken:                               # never surface an empty verdict
        spoken = ("The board was split." if len(speakers) >= 2
                  else "Only one advisor had standing here." if speakers
                  else "No advisor had doctrine that applied.")

    return ChairVerdict(spoken=spoken, detail=detail, unanimous=unanimous,
                        speakers=len(speakers), abstained=abstained, guard_fired=guard_fired)
