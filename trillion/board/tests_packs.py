"""
Tests for Layer 5: packs — widgets described only when their app is connected.

    python -m unittest trillion.board.tests_packs
"""
from __future__ import annotations

import unittest

from .packs import active_widget_types, CORE, PACKS
from .tools import build_show_description, DESC_BUDGET


class Packs(unittest.TestCase):
    def test_core_always_present(self):
        types = active_widget_types(set())
        for t in CORE:
            self.assertIn(t, types)

    def test_pack_widget_hidden_without_app(self):
        self.assertNotIn("inbox", active_widget_types(set()))
        self.assertNotIn("pipeline", active_widget_types({"calendar"}))

    def test_comms_pack_appears_with_mail(self):
        self.assertIn("inbox", active_widget_types({"mail"}))
        self.assertIn("inbox", active_widget_types({"calendar"}))

    def test_crm_pack_appears_with_crm(self):
        self.assertIn("pipeline", active_widget_types({"stripe"}))

    def test_canonical_order_preserved(self):
        types = active_widget_types({"mail", "crm"})
        self.assertEqual(types, sorted(types, key=_order))


def _order(t):
    from .widgets import WIDGET_TYPES
    return WIDGET_TYPES.index(t)


class Budget(unittest.TestCase):
    def test_each_pack_description_within_budget(self):
        # every pack switched on at once — the biggest description
        all_apps = {a for p in PACKS.values() for a in p["apps"]}
        desc = build_show_description(active_widget_types(all_apps))
        self.assertLess(len(desc), DESC_BUDGET)

    def test_core_only_description_within_budget(self):
        self.assertLess(len(build_show_description(active_widget_types(set()))), DESC_BUDGET)


if __name__ == "__main__":
    unittest.main()
