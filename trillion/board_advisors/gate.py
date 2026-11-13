"""
gate — the citation gate. The whole anti-fabrication design rests on this: a
seat may only cite the doctrine ids in its OWN dossier that it was actually
shown. Anything else — a fabricated id, a real id from another seat, an id
withheld from this one — is stripped server-side before the user ever sees it.

The gate can prove a citation EXISTS in the file. It can never prove the file is
TRUE; that is the fact-check's job (Tier 2). Keep the two separate.
"""
from __future__ import annotations


def gate_citations(cited, shown_ids) -> list[str]:
    """Return only the citations valid for this seat.

    `shown_ids` is what the seat was SHOWN (active doctrine), not everything in
    the file — the two diverge once entries can be retired. Uppercase-normalize,
    de-duplicate, preserve order; discard everything else.
    """
    valid = {str(i).strip().upper() for i in (shown_ids or [])}
    out: list[str] = []
    seen: set[str] = set()
    for c in (cited or []):
        k = str(c).strip().upper()
        if k in valid and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def is_unsourced(citations, abstained) -> bool:
    """True when a seat spoke (did not abstain) but cited nothing — talking
    without support. Not an error, but a flag the user should see at a glance."""
    return (not citations) and (not bool(abstained))
