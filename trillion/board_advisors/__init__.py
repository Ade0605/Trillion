"""
board_advisors — a board of advisors for Trillion: a standing council of
well-documented operators, each a dossier of numbered, sourced doctrine, each
convened as its OWN isolated model call. Two defences are structural, not
prompted: isolation (one call per seat, one dossier each) defeats consensus
theatre, and the citation gate defeats confident fabrication.

Tier 1 exports the dossier format + the gate.
"""
from __future__ import annotations

from .dossier import (parse_dossier, load_seat, Seat, Doctrine, DossierError,
                      VERIFICATION)
from .gate import gate_citations, is_unsourced

__all__ = ["parse_dossier", "load_seat", "Seat", "Doctrine", "DossierError",
           "VERIFICATION", "gate_citations", "is_unsourced"]
