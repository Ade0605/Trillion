"""
Tier 5 tests: the chair's deterministic guards (model injected).

    python -m unittest trillion.board_advisors.tests_tier5
"""
from __future__ import annotations

import json
import unittest

from .roster import load_roster
from .meeting import SeatOpinion
from .chair import synthesize

ROSTER = load_roster()


def chair_says(payload):
    return lambda user, system="", max_tokens=0: json.dumps(payload)


def spoke(seat_id, name, pos="a position"):
    return SeatOpinion(seat_id=seat_id, name=name, position=pos, citations=["D1"], confidence=0.6)


def abstain(seat_id, name):
    return SeatOpinion(seat_id=seat_id, name=name, abstained=True)


class Guards(unittest.TestCase):
    def test_one_speaker_is_never_unanimous(self):
        ops = [spoke("naval", "Naval Ravikant"), abstain("hormozi", "Alex Hormozi")]
        v = synthesize("q", ops, "brief", ROSTER,
                       complete_fn=chair_says({"spoken": "x", "unanimous": True}))
        self.assertFalse(v.unanimous)            # only one voice
        self.assertEqual(v.speakers, 1)
        self.assertEqual(v.abstained, ["Alex Hormozi"])

    def test_spoken_sanitized_when_verdict_not_unanimous(self):
        ops = [spoke("naval", "Naval Ravikant")]   # one speaker
        v = synthesize("q", ops, "brief", ROSTER,
                       complete_fn=chair_says({"spoken": "The board was unanimous on this.",
                                               "unanimous": True}))
        self.assertFalse(v.unanimous)
        self.assertNotRegex(v.spoken.lower(), r"unanimous")   # the prose was corrected
        self.assertTrue(v.guard_fired)

    def test_two_speakers_can_be_unanimous(self):
        ops = [spoke("naval", "Naval Ravikant"), spoke("hormozi", "Alex Hormozi")]
        v = synthesize("q", ops, "brief", ROSTER,
                       complete_fn=chair_says({"spoken": "Both agree.", "unanimous": True}))
        self.assertTrue(v.unanimous)
        self.assertEqual(v.speakers, 2)

    def test_empty_spoken_gets_a_fallback(self):
        ops = [spoke("naval", "Naval Ravikant"), spoke("hormozi", "Alex Hormozi")]
        v = synthesize("q", ops, "brief", ROSTER, complete_fn=chair_says({"unanimous": False}))
        self.assertTrue(v.spoken)                 # never empty

    def test_all_abstained(self):
        ops = [abstain("naval", "Naval Ravikant"), abstain("hormozi", "Alex Hormozi")]
        v = synthesize("q", ops, "brief", ROSTER, complete_fn=chair_says({"spoken": "", "unanimous": True}))
        self.assertFalse(v.unanimous)
        self.assertEqual(v.speakers, 0)


if __name__ == "__main__":
    unittest.main()
