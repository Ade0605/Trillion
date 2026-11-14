"""
Tier 4 tests: the isolated fan-out (model injected).

    python -m unittest trillion.board_advisors.tests_tier4
"""
from __future__ import annotations

import json
import unittest

from .roster import load_roster
from .meeting import hold_meeting, parse_opinion, ask_seat

ROSTER = load_roster()


def per_seat(mapping):
    """A fake model that answers by which seat's dossier is in the system prompt."""
    def fn(prompt, system="", max_tokens=0):
        for name, payload in mapping.items():
            if name in system:
                if isinstance(payload, Exception):
                    raise payload
                return json.dumps(payload)
        return json.dumps({"abstain": True})
    return fn


class Meeting(unittest.TestCase):
    def test_dedupe_seats(self):
        calls = {"n": 0}
        def fn(prompt, system="", max_tokens=0):
            calls["n"] += 1
            return json.dumps({"position": "x"})
        ops, _ = hold_meeting("q", ["naval", "naval", "hormozi"], ROSTER, "brief", complete_fn=fn)
        self.assertEqual(calls["n"], 2)          # naval not bought twice
        self.assertEqual(len(ops), 2)

    def test_ceiling_zero_spends_nothing(self):
        calls = {"n": 0}
        def fn(prompt, system="", max_tokens=0):
            calls["n"] += 1
            return "{}"
        ops, spent = hold_meeting("q", ["naval", "hormozi"], ROSTER, "brief",
                                  complete_fn=fn, cost_ceiling=0)
        self.assertEqual(calls["n"], 0)          # the check is BEFORE the call
        self.assertEqual(ops, [])
        self.assertEqual(spent, 0)

    def test_one_seat_failing_does_not_kill_the_meeting(self):
        fn = per_seat({"Naval Ravikant": RuntimeError("timeout"),
                       "Alex Hormozi": {"position": "charge more", "citations": ["D3"]}})
        ops, _ = hold_meeting("q", ["naval", "hormozi"], ROSTER, "brief", complete_fn=fn)
        self.assertEqual(len(ops), 2)
        byid = {o.seat_id: o for o in ops}
        self.assertTrue(byid["naval"].error)
        self.assertEqual(byid["hormozi"].citations, ["D3"])

    def test_citation_gate_applied_per_seat(self):
        s = ROSTER["hormozi"]
        op = parse_opinion(json.dumps({"position": "p", "citations": ["D1", "D9", "bogus"]}), s)
        self.assertEqual(op.citations, ["D1"])

    def test_abstain_string_false_is_not_abstention(self):
        s = ROSTER["naval"]
        op = parse_opinion(json.dumps({"position": "p", "abstain": "false", "citations": ["D1"]}), s)
        self.assertFalse(op.abstained)

    def test_confidence_coerced_and_clamped(self):
        s = ROSTER["naval"]
        self.assertEqual(parse_opinion(json.dumps({"confidence": "high"}), s).confidence, 0.0)
        self.assertEqual(parse_opinion(json.dumps({"confidence": 1.8}), s).confidence, 1.0)

    def test_abstention_marked_not_unsourced(self):
        s = ROSTER["naval"]
        op = parse_opinion(json.dumps({"abstain": True, "citations": []}), s)
        self.assertTrue(op.abstained)
        self.assertFalse(op.unsourced)           # abstaining is not "talking without support"


if __name__ == "__main__":
    unittest.main()
