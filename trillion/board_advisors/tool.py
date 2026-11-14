"""
tool — the `ask_board` tool. Convene the board on a real decision: route, fan out
in isolation (seats on the fast model), let the chair (the strong model, with the
live business brief) synthesize, store the meeting, and surface it the way
Trillion already surfaces things — as a card on the visual board. The model says
the chair's one short line; the detail is on screen.
"""
from __future__ import annotations

_SEAT_MODEL = "claude-haiku-4-5-20251001"
_CHAIR_MODEL = "claude-sonnet-4-6"
_USER_NAMES = ("bamidele", "adewale")
_COST_CEILING = 0.08                 # one meeting: ~router + 3 seats + chair


def _business_brief() -> str:
    """The live brief the chair reads — Starrdam's taught business knowledge."""
    try:
        from trillion.memory_store import FileMemoryStore
        from trillion.memory_recall import recall
        store = FileMemoryStore()
        res = recall("Starrdam business strategy competitors positioning sectors priorities",
                     store, k=8)
        lines = [f"- {m.hook}: {m.body}" for m in res.memories
                 if "starrdam" in (m.hook + m.body).lower()]
        return "\n".join(lines) or "No business brief available yet."
    except Exception:
        return "No business brief available yet."


def _surface(meeting: dict) -> None:
    """Put the meeting on the visual board (best-effort; never fails the tool)."""
    try:
        from trillion.board.state import BoardStore
        blocks = [{"block": "text", "text": meeting["spoken"]}]
        rows = []
        for o in meeting["opinions"]:
            if o["error"]:
                detail, meta = f"(no answer — {o['error']})", "error"
            elif o["abstained"]:
                detail, meta = "Abstained — no doctrine applied.", "abstained"
            else:
                detail = o["position"][:160]
                meta = ", ".join(o["citations"]) or "no citation"
            rows.append({"title": o["name"], "detail": detail, "meta": meta,
                         "tone": "attention" if o["abstained"] else None})
        blocks.append({"block": "rows", "items": rows})
        BoardStore().show([{"type": "custom", "title": "Board verdict",
                            "blocks": blocks, "source": "board of advisors"}], replace=False)
    except Exception:
        pass


def ask_board(question: str) -> str:
    from trillion.provider import complete
    from .convene import convene
    from .store import save_meeting

    def seat_cf(p, system="", max_tokens=1000):
        return complete(p, system=system, max_tokens=max_tokens, model=_SEAT_MODEL)

    def chair_cf(p, system="", max_tokens=1400):
        return complete(p, system=system, max_tokens=max_tokens, model=_CHAIR_MODEL)

    m = convene(question, seat_complete=seat_cf, chair_complete=chair_cf,
                business_brief=_business_brief(), user_names=_USER_NAMES,
                cost_ceiling=_COST_CEILING)
    if m.get("declined"):
        return f"The board didn't take this up — {m.get('reason') or 'not a board question'}."
    save_meeting(m)
    _surface(m)
    return f"[shown on the board] {m['spoken']}"


_DESCRIPTION = (
    "Convene the board of advisors on a real business decision. The board seats "
    "well-documented operators (Alex Hormozi — offers/pricing/lead-gen; Naval "
    "Ravikant — leverage/strategy; Rory Sutherland — positioning/differentiation). "
    "Each answers in ISOLATION from their own sourced doctrine and may abstain or "
    "disagree. Use when the user says 'ask the board', 'convene the board', or "
    "wants genuinely different outside reads on a strategic or business decision "
    "about their own company. Returns the chair's one-line synthesis; the full "
    "meeting (each advisor's position + citations) appears on the board."
)
_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string", "description": "the decision to put to the board"}},
    "required": ["question"],
}


def register_board_advisors(registry) -> None:
    registry.register(name="ask_board", description=_DESCRIPTION,
                      input_schema=_INPUT_SCHEMA, fn=ask_board)
