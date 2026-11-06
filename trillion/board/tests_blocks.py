"""
Tests for the block validators. Stdlib unittest.

    python -m unittest trillion.board.tests_blocks

Contract under test: length is forgiving (clip), structure is strict (refuse
with a message naming the fix), colour never leaks in (tone words only), unsafe
links are dropped, and the input is never mutated.
"""
from __future__ import annotations

import unittest

from . import caps
from .blocks import validate_block, validate_blocks, BlockError
from .samples import sample_blocks


class Value(unittest.TestCase):
    def test_minimal(self):
        out = validate_block({"block": "value", "label": "Revenue", "value": "$1k"})
        self.assertEqual(out, {"block": "value", "label": "Revenue", "value": "$1k"})

    def test_missing_value_refused_with_field(self):
        with self.assertRaises(BlockError) as e:
            validate_block({"block": "value", "label": "x"})
        self.assertIn("value", str(e.exception))

    def test_change_carries_tone_word_not_colour(self):
        out = validate_block({"block": "value", "value": "9", "change": "+3",
                              "changeTone": "#00ff00"})
        self.assertEqual(out["changeTone"], "neutral")   # bad tone → neutral, never a hex

    def test_long_title_is_clipped_not_rejected(self):
        out = validate_block({"block": "value", "label": "L" * 200, "value": "1"})
        self.assertLessEqual(len(out["label"]), caps.LABEL)
        self.assertTrue(out["label"].endswith("…"))


class Chart(unittest.TestCase):
    def test_series_required(self):
        with self.assertRaises(BlockError) as e:
            validate_block({"block": "chart", "kind": "line", "series": []})
        self.assertIn("series", str(e.exception))

    def test_series_capped_to_five(self):
        s = [{"name": str(i), "points": [1, 2]} for i in range(9)]
        out = validate_block({"block": "chart", "kind": "bar", "series": s})
        self.assertEqual(len(out["series"]), caps.MAX_SERIES)

    def test_number_as_text_is_coerced(self):
        out = validate_block({"block": "chart", "kind": "line",
                              "series": [{"points": ["1,200", "1300"]}]})
        self.assertEqual(out["series"][0]["points"], [1200.0, 1300.0])

    def test_bad_kind_refused(self):
        with self.assertRaises(BlockError):
            validate_block({"block": "chart", "kind": "pie", "series": [{"points": [1]}]})


class Table(unittest.TestCase):
    def test_rows_clamped_to_columns_and_cap(self):
        rows = [["a", "b", "c", "EXTRA"]] * 80
        out = validate_block({"block": "table", "columns": ["x", "y", "z"], "rows": rows})
        self.assertEqual(len(out["rows"]), caps.MAX_ROWS)
        self.assertEqual(len(out["rows"][0]), 3)          # extra cell dropped


class MeterAndLinks(unittest.TestCase):
    def test_meter_value_clamped_0_100(self):
        self.assertEqual(validate_block({"block": "meter", "value": 240})["value"], 100.0)
        self.assertEqual(validate_block({"block": "meter", "value": -5})["value"], 0.0)

    def test_unsafe_link_dropped(self):
        out = validate_block({"block": "text", "text": "hi", "link": "javascript:alert(1)"})
        self.assertNotIn("link", out)

    def test_http_link_kept(self):
        out = validate_block({"block": "text", "text": "hi", "link": "https://example.com"})
        self.assertEqual(out["link"], "https://example.com")


class Structure(unittest.TestCase):
    def test_unknown_block_refused(self):
        with self.assertRaises(BlockError) as e:
            validate_block({"block": "sparkline"})
        self.assertIn("unknown block", str(e.exception))

    def test_input_not_mutated(self):
        raw = {"block": "value", "label": "A", "value": "1", "extra": "keep"}
        validate_block(raw)
        self.assertEqual(raw, {"block": "value", "label": "A", "value": "1", "extra": "keep"})

    def test_bool_is_not_a_number(self):
        with self.assertRaises(BlockError):
            validate_block({"block": "meter", "value": True})


class Samples(unittest.TestCase):
    def test_every_sample_validates(self):
        blocks = sample_blocks()
        self.assertEqual(len(blocks), 11)
        for b in blocks:
            self.assertIn("block", b)

    def test_validate_blocks_list(self):
        out = validate_blocks([{"block": "text", "text": "a"}, {"block": "text", "text": "b"}])
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
