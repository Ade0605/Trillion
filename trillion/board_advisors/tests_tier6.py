"""
Tier 6 tests: convene snapshot, store roundtrip, retire-never-delete, edit drops
verification. Model injected; file edits run on a temp copy of the seats.

    python -m unittest trillion.board_advisors.tests_tier6
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from .roster import load_roster
from .convene import convene
from .store import save_meeting, list_meetings
from .edit import retire_entry, edit_entry
from .dossier import parse_dossier

ROSTER = load_roster()
_SEATS = Path(__file__).parent / "seats"


def combined(seats, per_seat):
    def fn(prompt, system="", max_tokens=0):
        if "route a question" in system.lower():
            return json.dumps({"decline": False, "seats": seats})
        for name, payload in per_seat.items():
            if name in system:
                return json.dumps(payload)
        return json.dumps({"abstain": True})
    return fn


class Convene(unittest.TestCase):
    def test_snapshots_citations_with_title_and_source(self):
        seat_cf = combined(["hormozi", "naval"], {
            "Alex Hormozi": {"position": "charge more", "citations": ["D3", "D99"]},
            "Naval Ravikant": {"abstain": True}})
        chair_cf = lambda u, system="", max_tokens=0: json.dumps({"spoken": "split", "unanimous": False})
        m = convene("should I raise prices?", seat_complete=seat_cf, chair_complete=chair_cf,
                    business_brief="brief", roster=ROSTER)
        self.assertFalse(m["declined"])
        snap = {c["id"]: c for c in m["citations"]}
        self.assertIn("D3", snap)                       # D99 was fabricated → gated out
        self.assertNotIn("D99", snap)
        self.assertTrue(snap["D3"]["title"] and snap["D3"]["source"])
        self.assertIn("Naval Ravikant", m["abstained"])

    def test_declined_question_returns_reason(self):
        seat_cf = lambda p, system="", max_tokens=0: json.dumps({"decline": True, "decline_reason": "medical"})
        m = convene("my tooth hurts", seat_complete=seat_cf, chair_complete=seat_cf,
                    business_brief="b", roster=ROSTER)
        self.assertTrue(m["declined"])


class Store(unittest.TestCase):
    def test_roundtrip(self):
        tmp = Path(tempfile.mkdtemp()) / "m.json"
        mid = save_meeting({"question": "q", "spoken": "s"}, path=tmp)
        got = list_meetings(path=tmp)
        self.assertEqual(got[0]["id"], mid)
        self.assertEqual(got[0]["question"], "q")


class Edits(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        for f in _SEATS.glob("*.md"):
            shutil.copy(f, self.dir / f.name)

    def test_retire_keeps_id_but_withholds_from_meetings(self):
        retire_entry("hormozi", "D1", directory=self.dir)
        seat = parse_dossier((self.dir / "hormozi.md").read_text(encoding="utf-8"), slug="hormozi")
        self.assertIn("D1", seat.ids)                   # id stays spoken-for
        self.assertNotIn("D1", seat.shown_ids())        # withheld from meetings
        d1 = next(d for d in seat.doctrine if d.id == "D1")
        self.assertEqual(d1.verification, "retired")

    def test_edit_drops_verification_to_user(self):
        seat0 = parse_dossier((self.dir / "hormozi.md").read_text(encoding="utf-8"), slug="h")
        self.assertEqual(next(d for d in seat0.doctrine if d.id == "D2").verification, "sourced")
        edit_entry("hormozi", "D2", "A new claim I typed myself.", directory=self.dir)
        seat1 = parse_dossier((self.dir / "hormozi.md").read_text(encoding="utf-8"), slug="h")
        d2 = next(d for d in seat1.doctrine if d.id == "D2")
        self.assertEqual(d2.verification, "user")       # server drops it; can't stay 'sourced'
        self.assertIn("new claim", d2.body)
        self.assertIn("D2", seat1.shown_ids())          # still citable, just unverified


if __name__ == "__main__":
    unittest.main()
