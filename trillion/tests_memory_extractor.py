"""
Tests for the memory extractor and its approval queue. Stdlib unittest.

    python -m unittest trillion.tests_memory_extractor

The model call is injected, so these are offline and deterministic.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import memory_extractor as mx
from .memory_store import FileMemoryStore


def _completer(payload):
    return lambda prompt, system="": payload


class Extract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FileMemoryStore(root=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def _convo(self, *pairs):
        msgs = []
        for u, a in pairs:
            msgs.append({"role": "user", "content": u})
            msgs.append({"role": "assistant", "content": a})
        return msgs

    def test_skips_thin_sessions(self):
        msgs = self._convo(("hi", "hello"))
        out = mx.extract(msgs, self.store, completer=_completer("should not be called"))
        self.assertEqual(out, [])

    def test_extracts_durable_facts(self):
        msgs = self._convo(
            ("I work at Acme as a designer", "Noted."),
            ("Remember I prefer dark mode", "Got it."),
        )
        payload = ('[{"hook":"Works at Acme as a designer","body":"...","type":"user"},'
                   '{"hook":"Prefers dark mode","body":"...","type":"feedback"}]')
        out = mx.extract(msgs, self.store, completer=_completer(payload))
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["type"], "user")
        self.assertEqual(out[1]["type"], "feedback")

    def test_dedupes_against_existing(self):
        self.store.add(hook="Prefers dark mode", body="x", mtype="feedback")
        msgs = self._convo(("chat one", "reply"), ("chat two", "reply"))
        out = mx.extract(msgs, self.store,
                         completer=_completer('[{"hook":"prefers dark mode","body":"y","type":"feedback"}]'))
        self.assertEqual(out, [])                     # near-duplicate rejected

    def test_ignores_tool_rounds(self):
        msgs = [
            {"role": "user", "content": "what's due"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": "x", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "none"}]},
            {"role": "assistant", "content": "Nothing due."},
            {"role": "user", "content": "ok thanks"},
        ]
        captured = {}

        def cap(prompt, system=""):
            captured["prompt"] = prompt
            return "[]"
        mx.extract(msgs, self.store, completer=cap)
        self.assertNotIn("tool_use", captured.get("prompt", ""))
        self.assertNotIn("tool_result", captured.get("prompt", ""))

    def test_malformed_model_output_is_empty(self):
        msgs = self._convo(("a real message here", "ok"), ("another one", "ok"))
        self.assertEqual(mx.extract(msgs, self.store, completer=_completer("not json at all")), [])

    def test_empty_array(self):
        msgs = self._convo(("just chatting about weather", "yeah"), ("nothing durable", "right"))
        self.assertEqual(mx.extract(msgs, self.store, completer=_completer("[]")), [])


class Queue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = FileMemoryStore(root=self.root / "memory")
        self._patch = mock.patch.object(mx, "_PENDING", self.root / "pending.json")
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self.tmp.cleanup()

    def test_enqueue_then_approve_writes_a_memory(self):
        n = mx.enqueue([{"hook": "Lives in Lagos", "body": "b", "type": "user"}], source="test")
        self.assertEqual(n, 1)
        items = mx.list_pending()
        self.assertEqual(len(items), 1)
        self.assertTrue(mx.approve(items[0]["id"], self.store))
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(mx.list_pending(), [])       # removed from queue

    def test_reject_drops_without_writing(self):
        mx.enqueue([{"hook": "temp", "body": "b", "type": "user"}])
        item_id = mx.list_pending()[0]["id"]
        self.assertTrue(mx.reject(item_id))
        self.assertEqual(self.store.count(), 0)
        self.assertEqual(mx.list_pending(), [])

    def test_enqueue_dedupes_identical_hooks(self):
        mx.enqueue([{"hook": "same", "body": "1", "type": "user"}])
        added = mx.enqueue([{"hook": "same", "body": "2", "type": "user"}])
        self.assertEqual(added, 0)
        self.assertEqual(len(mx.list_pending()), 1)

    def test_approve_unknown_id_is_false(self):
        self.assertFalse(mx.approve("nope", self.store))


if __name__ == "__main__":
    unittest.main()
