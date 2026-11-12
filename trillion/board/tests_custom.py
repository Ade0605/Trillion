"""
Tests for Layer 6: the custom widget (blocks supplied directly, same validators).

    python -m unittest trillion.board.tests_custom
"""
from __future__ import annotations

import unittest

from .widgets import build_widget, WidgetError


class Custom(unittest.TestCase):
    def test_custom_expands_its_blocks(self):
        w = build_widget({"type": "custom", "title": "Mix", "blocks": [
            {"block": "value", "label": "A", "value": "1"},
            {"block": "chips", "items": [{"text": "x"}]},
        ]})
        self.assertEqual(w["type"], "custom")
        self.assertEqual([b["block"] for b in w["blocks"]], ["value", "chips"])

    def test_custom_blocks_are_validated(self):
        # a bad block inside custom is refused by the same validator
        with self.assertRaises(WidgetError):
            build_widget({"type": "custom", "blocks": [{"block": "value", "label": "x"}]})

    def test_custom_unknown_block_refused(self):
        with self.assertRaises(WidgetError):
            build_widget({"type": "custom", "blocks": [{"block": "sparkline"}]})

    def test_custom_requires_blocks(self):
        with self.assertRaises(WidgetError) as e:
            build_widget({"type": "custom", "title": "x"})
        self.assertIn("blocks", str(e.exception))


if __name__ == "__main__":
    unittest.main()
