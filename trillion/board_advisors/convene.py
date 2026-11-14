"""
convene — the full pipeline: route → isolated fan-out → chair. Returns a Meeting
record with each cited entry's title and source SNAPSHOTTED in, so a stored
meeting renders its own citations without re-reading the dossier and stays
readable after the files change.
"""
from __future__ import annotations

import time

from .roster import load_roster
from .routing import route
from .meeting import hold_meeting
from .chair import synthesize


def _op_dict(o) -> dict:
    return {"seat_id": o.seat_id, "name": o.name, "position": o.position,
            "reasoning": o.reasoning, "citations": o.citations,
            "confidence": o.confidence, "change_mind": o.change_mind,
            "abstained": o.abstained, "unsourced": o.unsourced, "error": o.error}


def _snapshot_citations(opinions, roster) -> list[dict]:
    """Freeze the title+source of every cited entry into the meeting."""
    snap: list[dict] = []
    for o in opinions:
        seat = roster.get(o.seat_id)
        if not seat:
            continue
        by = {d.id: d for d in seat.doctrine}
        for cid in o.citations:
            d = by.get(cid)
            if d:
                snap.append({"advisor": seat.name, "id": cid, "title": d.title,
                             "source": d.source, "verification": d.verification})
    return snap


def convene(question, *, seat_complete, chair_complete, business_brief,
            roster=None, user_names=(), cost_ceiling=None) -> dict:
    roster = roster or load_roster()
    r = route(question, roster, complete_fn=seat_complete, user_names=user_names)
    if not r.is_board_question:
        return {"declined": True, "reason": r.decline_reason, "question": question,
                "ts": time.time()}

    opinions, spent = hold_meeting(question, r.seat_ids, roster, business_brief,
                                   complete_fn=seat_complete, cost_ceiling=cost_ceiling)
    verdict = synthesize(question, opinions, business_brief, roster, complete_fn=chair_complete)

    return {
        "declined": False, "question": question, "ts": time.time(),
        "seat_ids": [o.seat_id for o in opinions],
        "named": r.named,
        "opinions": [_op_dict(o) for o in opinions],
        "spoken": verdict.spoken, "detail": verdict.detail,
        "unanimous": verdict.unanimous, "speakers": verdict.speakers,
        "abstained": verdict.abstained, "guard_fired": verdict.guard_fired,
        "citations": _snapshot_citations(opinions, roster),
        "cost": round(spent, 5),
    }
