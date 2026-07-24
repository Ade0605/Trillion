"""
Tests for working-memory persistence. Stdlib unittest.

    python -m unittest trillion.tests_sessions

Pins two things: the session store round-trips and resolves correctly, and the
window bounding NEVER splits a tool_use/tool_result pair — a wrong cut there
re-creates the orphaned-tool_use 400 that tests_agent_history guards.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from .agent import Agent
from .sessions import IDLE_RESET_SECONDS, SessionStore


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SessionStore(root=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_resolve_is_new(self):
        sid, is_new = self.store.resolve_active()
        self.assertTrue(is_new)
        self.assertTrue(sid)

    def test_reuse_within_idle_window(self):
        sid, _ = self.store.resolve_active()
        self.store.save(sid, [{"role": "user", "content": "hi"}])
        sid2, is_new = self.store.resolve_active()
        self.assertEqual(sid, sid2)
        self.assertFalse(is_new)

    def test_new_session_after_idle(self):
        sid, _ = self.store.resolve_active()
        self.store.save(sid, [{"role": "user", "content": "hi"}])
        # backdate current.json beyond the idle window
        import json
        cf = Path(self.tmp.name) / "current.json"
        cf.write_text(json.dumps({"id": sid, "last_active": time.time() - IDLE_RESET_SECONDS - 5}))
        sid2, is_new = self.store.resolve_active()
        self.assertNotEqual(sid, sid2)
        self.assertTrue(is_new)

    def test_save_load_roundtrip(self):
        sid, _ = self.store.resolve_active()
        msgs = [
            {"role": "user", "content": "what's due?"},
            {"role": "assistant", "content": "Nothing today."},
        ]
        self.store.save(sid, msgs)
        self.assertEqual(self.store.load(sid), msgs)

    def test_load_unknown_is_empty(self):
        self.assertEqual(self.store.load("nope"), [])


class BoundWindow(unittest.TestCase):
    def _agent(self, limit):
        a = Agent.__new__(Agent)
        a._max_window = limit
        a.conversation = []
        return a

    def test_keeps_whole_turns(self):
        a = self._agent(4)
        # 3 simple turns (6 messages), limit 4 → keep last 2 turns (4 msgs)
        a.conversation = [
            {"role": "user", "content": "one"}, {"role": "assistant", "content": "1"},
            {"role": "user", "content": "two"}, {"role": "assistant", "content": "2"},
            {"role": "user", "content": "three"}, {"role": "assistant", "content": "3"},
        ]
        a._bound_window()
        self.assertEqual(len(a.conversation), 4)
        self.assertEqual(a.conversation[0]["content"], "two")

    def test_never_splits_a_tool_pair(self):
        """The window must start on a real user turn, never on a tool_result —
        an orphaned tool_use bricks the next API call."""
        a = self._agent(3)
        a.conversation = [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "old reply"},
            {"role": "user", "content": "list my reminders"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "list_reminders", "input": {}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "none"}]},
            {"role": "assistant", "content": "You're clear."},
        ]
        a._bound_window()
        # window must begin at the "list my reminders" user turn, keeping the
        # tool_use and its tool_result together
        self.assertEqual(a.conversation[0]["content"], "list my reminders")
        # no orphaned tool_use
        ids = [b["id"] for m in a.conversation if isinstance(m["content"], list)
               for b in m["content"] if b.get("type") == "tool_use"]
        results = [b["tool_use_id"] for m in a.conversation if isinstance(m["content"], list)
                   for b in m["content"] if b.get("type") == "tool_result"]
        self.assertEqual(set(ids), set(results))

    def test_under_limit_untouched(self):
        a = self._agent(40)
        conv = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hey"}]
        a.conversation = list(conv)
        a._bound_window()
        self.assertEqual(a.conversation, conv)


class AgentIntegration(unittest.TestCase):
    def test_resume_reloads_and_reset_starts_fresh(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = SessionStore(root=Path(tmp.name))

        a = Agent.__new__(Agent)
        a._max_window = 40
        a.conversation = []
        a._sessions = None
        a._session_id = None
        a.attach_sessions(store)
        first_sid = a._session_id
        a.conversation = [{"role": "user", "content": "remember: sky is blue"}]
        a._persist()

        # a "restart": brand-new agent, same store → thread comes back
        b = Agent.__new__(Agent)
        b._max_window = 40
        b.conversation = []
        b._sessions = None
        b._session_id = None
        b.attach_sessions(store)
        self.assertEqual(b._session_id, first_sid)
        self.assertEqual(b.conversation[0]["content"], "remember: sky is blue")

        # reset → new session id, empty thread
        b.reset()
        self.assertNotEqual(b._session_id, first_sid)
        self.assertEqual(b.conversation, [])


if __name__ == "__main__":
    unittest.main()
