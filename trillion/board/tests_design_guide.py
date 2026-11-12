"""
Tests for Layer 4: the design guide names every block and widget, and the style
page's data comes from the server's own samples (so it can't drift).

    python -m unittest trillion.board.tests_design_guide
"""
from __future__ import annotations

import unittest

from .blocks import BLOCK_TYPES
from .widgets import WIDGET_TYPES
from .design_guide import design_guide
from .samples import sample_widgets, sample_blocks


class Guide(unittest.TestCase):
    def test_names_every_block(self):
        g = design_guide()
        for b in BLOCK_TYPES:
            self.assertIn(b, g, b)

    def test_names_every_widget(self):
        g = design_guide()
        for w in WIDGET_TYPES:
            self.assertIn(w, g, w)

    def test_explains_how_to_add(self):
        self.assertIn("Adding a widget", design_guide())


class StylePageSource(unittest.TestCase):
    def test_one_sample_per_widget(self):
        self.assertEqual(len(sample_widgets()), len(WIDGET_TYPES))

    def test_one_sample_per_block(self):
        self.assertEqual(len(sample_blocks()), len(BLOCK_TYPES))

    def test_samples_are_validated_widgets(self):
        for w in sample_widgets():
            self.assertIn("blocks", w)
            self.assertTrue(w["blocks"])


if __name__ == "__main__":
    unittest.main()
