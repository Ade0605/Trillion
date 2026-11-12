"""
Tests for Layer 2: widgets validate + expand into blocks.

    python -m unittest trillion.board.tests_widgets
"""
from __future__ import annotations

import unittest

from .widgets import build_widget, build_board, WidgetError, strip_emoji
from . import caps


def _types(widget):
    return [b["block"] for b in widget["blocks"]]


class NearMiss(unittest.TestCase):
    def test_kpi_means_stat(self):
        w = build_widget({"type": "kpi", "label": "Revenue", "value": "$1k"})
        self.assertEqual(w["type"], "stat")
        self.assertEqual(_types(w), ["value"])

    def test_stat_title_falls_back_to_label(self):
        w = build_widget({"type": "stat", "title": "Revenue this year", "value": "$1k"})
        self.assertEqual(w["blocks"][0]["label"], "Revenue this year")

    def test_flat_data_without_data_key(self):
        w = build_widget({"type": "stat", "value": "9", "delta": "+1", "tone": "good"})
        self.assertEqual(w["blocks"][0]["value"], "9")
        self.assertEqual(w["blocks"][0]["change"], "+1")


class Expansion(unittest.TestCase):
    def test_next_up_is_timeline(self):
        w = build_widget({"type": "schedule", "events": [{"time": "9am", "title": "Standup"}]})
        self.assertEqual(w["type"], "next-up")
        self.assertEqual(_types(w), ["timeline"])

    def test_inbox_is_rows(self):
        w = build_widget({"type": "emails", "items": [{"subject": "Hi", "from": "Sam"}]})
        self.assertEqual(_types(w), ["rows"])

    def test_pipeline_is_table(self):
        w = build_widget({"type": "deals", "deals": [{"name": "A", "stage": "Won", "value": "$5k"}]})
        self.assertEqual(_types(w), ["table"])
        self.assertEqual(w["blocks"][0]["columns"], ["Deal", "Stage", "Value"])

    def test_goal_is_ring_meter(self):
        w = build_widget({"type": "goal", "value": 68, "caption": "68%"})
        self.assertEqual(w["blocks"][0]["block"], "meter")
        self.assertEqual(w["blocks"][0]["kind"], "ring")

    def test_risk_meter_is_bar(self):
        w = build_widget({"type": "risk", "value": 40})
        self.assertEqual(w["blocks"][0]["kind"], "bar")

    def test_sector_is_value_plus_text(self):
        w = build_widget({"type": "sector", "sector": "Aviation", "note": "orphaned"})
        self.assertEqual(_types(w), ["value", "text"])

    def test_brief_text_and_chips(self):
        w = build_widget({"type": "brief", "text": "Quiet day.", "points": ["a", "b"]})
        self.assertEqual(_types(w), ["text", "chips"])


class Stamping(unittest.TestCase):
    def test_source_and_time_stamped(self):
        w = build_widget({"type": "stat", "value": "9", "source": "Stripe"}, now="3 min ago")
        self.assertEqual(w["source"], "Stripe")
        self.assertEqual(w["updated"], "3 min ago")

    def test_emoji_stripped_symbols_kept(self):
        self.assertEqual(strip_emoji("Revenue 🚀 up ↑"), "Revenue  up ↑")
        w = build_widget({"type": "stat", "title": "Sales 🎉", "value": "$1k ↑"})
        self.assertNotIn("🎉", w["title"])
        self.assertIn("↑", w["blocks"][0]["value"])


class Errors(unittest.TestCase):
    def test_unknown_type_names_options(self):
        with self.assertRaises(WidgetError) as e:
            build_widget({"type": "wormhole", "value": "1"})
        self.assertIn("unknown widget type", str(e.exception))

    def test_stat_without_value_names_field(self):
        with self.assertRaises(WidgetError) as e:
            build_widget({"type": "stat", "label": "x"})
        self.assertIn("value", str(e.exception))

    def test_board_capped_at_twelve(self):
        ws = [{"type": "stat", "value": str(i)} for i in range(20)]
        self.assertEqual(len(build_board(ws)), caps.MAX_WIDGETS)


if __name__ == "__main__":
    unittest.main()
