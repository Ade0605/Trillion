"""
roster — load every dossier in seats/ into a {id: Seat} map. A file that fails
to parse loses its own seat with a logged warning (see load_seat); the roster
never raises and never silently shrinks without a log.
"""
from __future__ import annotations

from pathlib import Path

from .dossier import load_seat, Seat

_SEATS_DIR = Path(__file__).parent / "seats"


def load_roster(directory: Path | None = None) -> dict[str, Seat]:
    d = Path(directory) if directory else _SEATS_DIR
    seats: dict[str, Seat] = {}
    if not d.exists():
        return seats
    for f in sorted(d.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        seat = load_seat(text, slug=f.stem)
        if seat is not None:
            seats[seat.id] = seat
    return seats
