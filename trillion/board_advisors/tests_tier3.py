"""
Tier 3 tests: routing + the decline gate (deterministic; model injected).

    python -m unittest trillion.board_advisors.tests_tier3
"""
from __future__ import annotations

import json
import unittest

from .roster import load_roster
from .routing import route, match_names, normalize, parse_router, _coerce_bool

ROSTER = load_roster()


def fake(payload):
    return lambda prompt, system="": json.dumps(payload)


class Names(unittest.TestCase):
    def test_named_advisor_matched(self):
        self.assertIn("hormozi", match_names("what would Hormozi say about pricing?", ROSTER))
        self.assertIn("naval", match_names("ask Naval about leverage", ROSTER))

    def test_curly_apostrophe_normalized(self):
        self.assertEqual(normalize("O’Leary"), "O'Leary")

    def test_user_name_collision_does_not_route(self):
        # if the user's own name token matches an advisor token, it must not route
        self.assertNotIn("sutherland", match_names("ask rory to do it", ROSTER, user_names=["rory"]))


class Route(unittest.TestCase):
    def test_named_overrides_decline(self):
        # router says decline, but the user explicitly named Hormozi
        r = route("what would Hormozi think?", ROSTER, complete_fn=fake({"decline": True}))
        self.assertTrue(r.is_board_question)
        self.assertEqual(r.named, ["hormozi"])

    def test_router_picks_seats_by_domain(self):
        r = route("how should I position against competitors?", ROSTER,
                  complete_fn=fake({"decline": False, "seats": ["sutherland", "naval"]}))
        self.assertTrue(r.is_board_question)
        self.assertEqual(set(r.seat_ids), {"sutherland", "naval"})

    def test_decline_is_respected_when_not_named(self):
        r = route("fix this python traceback", ROSTER,
                  complete_fn=fake({"decline": True, "decline_reason": "software/technical"}))
        self.assertFalse(r.is_board_question)
        self.assertIn("technical", r.decline_reason)

    def test_capped_at_four(self):
        r = route("big strategy question", ROSTER,
                  complete_fn=fake({"decline": False, "seats": ["naval", "hormozi", "sutherland", "naval"]}))
        self.assertLessEqual(len(r.seat_ids), 4)

    def test_unknown_seat_ids_dropped(self):
        _, _, ids = parse_router(json.dumps({"seats": ["naval", "elon", "ghost"]}), ROSTER)
        self.assertEqual(ids, ["naval"])

    def test_string_false_coerced(self):
        self.assertFalse(_coerce_bool("false"))
        self.assertTrue(_coerce_bool("true"))
        self.assertFalse(_coerce_bool(None))


if __name__ == "__main__":
    unittest.main()
