"""
Tier 2 tests: the researched roster loads and every seat is well-formed.

    python -m unittest trillion.board_advisors.tests_tier2
"""
from __future__ import annotations

import unittest

from .roster import load_roster

ROSTER = load_roster()


class Roster(unittest.TestCase):
    def test_three_seats_loaded(self):
        self.assertEqual(set(ROSTER), {"hormozi", "naval", "sutherland"})

    def test_every_seat_is_complete(self):
        for sid, s in ROSTER.items():
            self.assertTrue(s.domains, sid)
            self.assertTrue(s.doctrine, sid)
            self.assertTrue(s.blind_spots, f"{sid} must declare blind spots")
            self.assertTrue(s.objection, f"{sid} must have a characteristic objection")
            self.assertTrue(s.voice, sid)

    def test_no_duplicate_ids_in_any_seat(self):
        for sid, s in ROSTER.items():
            ids = [d.id for d in s.doctrine]
            self.assertEqual(len(ids), len(set(ids)), sid)

    def test_every_entry_has_a_source(self):
        for sid, s in ROSTER.items():
            for d in s.doctrine:
                self.assertTrue(d.source, f"{sid} {d.id} has no source")

    def test_sutherland_signalling_credits_origin(self):
        # the adversarial catch must stay in the file: D3 credits biology/econ
        d3 = next(d for d in ROSTER["sutherland"].doctrine if d.id == "D3")
        self.assertRegex(d3.source.lower() + d3.body.lower(), r"zahavi|spence|did not originate")


if __name__ == "__main__":
    unittest.main()
