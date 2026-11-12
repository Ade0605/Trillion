"""
Tests for Layer 3: live board state + the show/update/remove tools.

    python -m unittest trillion.board.tests_state
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from . import caps
from .state import BoardStore
from .tools import register_board_tools, SHOW_DESCRIPTION, DESC_BUDGET, _WIDGET_ITEM


class _Registry:
    def __init__(self):
        self.tools = {}

    def register(self, *, name, description, input_schema, fn):
        self.tools[name] = {"description": description, "schema": input_schema, "fn": fn}


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = BoardStore(path=Path(self.tmp.name) / "board.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_show_replaces_and_assigns_ids(self):
        out = self.store.show([{"type": "stat", "title": "Rev", "value": "$1"}])
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["id"])
        self.assertEqual(self.store.snapshot()[0]["title"], "Rev")

    def test_show_append_and_cap(self):
        self.store.show([{"type": "stat", "value": "1"}])
        for _ in range(20):
            self.store.show([{"type": "stat", "value": "x"}], replace=False)
        self.assertEqual(len(self.store.snapshot()), caps.MAX_WIDGETS)

    def test_update_keeps_id(self):
        wid = self.store.show([{"type": "stat", "title": "A", "value": "1"}])[0]["id"]
        self.store.update(wid, {"type": "stat", "title": "B", "value": "2"})
        snap = self.store.snapshot()
        self.assertEqual(snap[0]["id"], wid)
        self.assertEqual(snap[0]["title"], "B")

    def test_remove(self):
        ids = [w["id"] for w in self.store.show(
            [{"type": "stat", "value": "1"}, {"type": "stat", "value": "2"}])]
        removed = self.store.remove([ids[0]])
        self.assertEqual(removed, [ids[0]])
        self.assertEqual(len(self.store.snapshot()), 1)


class Tools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = _Registry()
        register_board_tools(self.reg, BoardStore(path=Path(self.tmp.name) / "b.json"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_show_tool_one_line_result(self):
        out = self.reg.tools["board_show"]["fn"](
            [{"type": "stat", "title": "Revenue", "value": "$1k"}])
        self.assertIn("On the board now: Revenue", out)

    def test_show_tool_names_bad_field(self):
        out = self.reg.tools["board_show"]["fn"]([{"type": "stat", "label": "x"}])
        self.assertIn("value", out)

    def test_three_tools_registered(self):
        self.assertEqual(set(self.reg.tools), {"board_show", "board_update", "board_remove"})


class Schema(unittest.TestCase):
    def test_description_within_budget(self):
        self.assertLess(len(SHOW_DESCRIPTION), DESC_BUDGET)

    def test_schema_is_flat_no_oneof_enum(self):
        blob = json.dumps(_WIDGET_ITEM)
        for forbidden in ("oneOf", "anyOf", "allOf", "enum"):
            self.assertNotIn(forbidden, blob)


if __name__ == "__main__":
    unittest.main()
