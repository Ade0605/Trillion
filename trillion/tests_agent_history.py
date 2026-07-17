"""
Tests locking in tool_use / tool_result pairing in the conversation. Stdlib unittest.

    python -m unittest trillion.tests_agent_history

Why this exists: run_turn is a generator. If the SSE client disconnects mid
tool-loop (page reload, tab close, an unanswered confirm prompt), the generator
is closed after the assistant `tool_use` message is written but before the
`tool_result` round. The orphaned tool_use then makes EVERY later request fail
with `400 invalid_request_error: tool_use ids were found without tool_result
blocks`. The conversation is bricked until reset.

Two guarantees are pinned here:
  1. run_turn never leaves an orphan, even when closed mid-loop (the finally).
  2. _repair_conversation heals a history that is already orphaned.
"""
from __future__ import annotations

import unittest

from .agent import Agent


def _orphan_ids(conversation: list) -> list:
    """Every tool_use id lacking a tool_result in the following message."""
    orphans = []
    for i, m in enumerate(conversation):
        content = m.get("content")
        if m.get("role") != "assistant" or not isinstance(content, list):
            continue
        ids = [b.get("id") for b in content
               if isinstance(b, dict) and b.get("type") == "tool_use"]
        if not ids:
            continue
        nxt = conversation[i + 1] if i + 1 < len(conversation) else None
        have = set()
        if nxt and nxt.get("role") == "user" and isinstance(nxt.get("content"), list):
            have = {b.get("tool_use_id") for b in nxt["content"]
                    if isinstance(b, dict) and b.get("type") == "tool_result"}
        orphans += [t for t in ids if t not in have]
    return orphans


class RepairsExistingOrphans(unittest.TestCase):
    def setUp(self):
        self.agent = Agent.__new__(Agent)          # no API key needed for repair
        self.agent.conversation = []

    def test_orphaned_tool_use_gets_a_result(self):
        self.agent.conversation = [
            {"role": "user", "content": "what's due today?"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_01ABC", "name": "list_reminders", "input": {}},
            ]},
        ]
        n = self.agent._repair_conversation()
        self.assertEqual(n, 1)
        self.assertEqual(_orphan_ids(self.agent.conversation), [])

    def test_partial_results_are_topped_up(self):
        """Two tool_use blocks but only one result → the missing one is filled."""
        self.agent.conversation = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_A", "name": "list_notes", "input": {}},
                {"type": "tool_use", "id": "toolu_B", "name": "list_reminders", "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_A", "content": "ok"},
            ]},
        ]
        n = self.agent._repair_conversation()
        self.assertEqual(n, 1)
        self.assertEqual(_orphan_ids(self.agent.conversation), [])
        # topped up in place — no stray extra user message
        self.assertEqual(len(self.agent.conversation), 3)

    def test_healthy_history_is_untouched(self):
        clean = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_A", "name": "list_notes", "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_A", "content": "ok"},
            ]},
            {"role": "assistant", "content": "You have no notes."},
        ]
        self.agent.conversation = [dict(m) for m in clean]
        self.assertEqual(self.agent._repair_conversation(), 0)
        self.assertEqual(self.agent.conversation, clean)

    def test_plain_text_history_is_untouched(self):
        self.agent.conversation = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hello."},
        ]
        self.assertEqual(self.agent._repair_conversation(), 0)
        self.assertEqual(len(self.agent.conversation), 2)


class InterruptedTurnLeavesNoOrphan(unittest.TestCase):
    """The real-world failure: the client hangs up while a tool is running."""

    def test_generator_closed_mid_tool_loop_still_pairs(self):
        agent = Agent.__new__(Agent)
        agent.conversation = []
        agent.model = "test-model"
        agent.max_tool_calls = 5
        agent._tool_registry = None
        agent._confirm_waiter = lambda n, i: True

        # Stub the model: one tool_use, then a plain reply.
        def fake_send_turn(messages, system, model, tools):
            yield {"tool_use": {"id": "toolu_XYZ", "name": "list_reminders", "input": {}}}

        agent._system_blocks = lambda: []
        agent._anthropic_tools = lambda: []
        agent._run_tool = lambda name, inp: "some result"

        import trillion.agent as agent_mod
        real_send, real_cue = agent_mod.send_turn, None
        agent_mod.send_turn = fake_send_turn
        try:
            from trillion import personality
            real_cue = personality.append_voice_cue
            personality.append_voice_cue = lambda msgs: msgs

            gen = agent.run_turn("what's due?")
            # Consume only up to the first yield (the tool_start), then hang up —
            # exactly what a browser reload does mid-stream.
            next(gen)
            gen.close()
        finally:
            agent_mod.send_turn = real_send
            if real_cue:
                from trillion import personality
                personality.append_voice_cue = real_cue

        # Guard against a vacuous pass: the tool_use MUST have been written, so
        # that "no orphans" means "it was paired", not "it never happened".
        wrote_tool_use = any(
            m.get("role") == "assistant" and isinstance(m.get("content"), list)
            and any(b.get("type") == "tool_use" for b in m["content"])
            for m in agent.conversation
        )
        self.assertTrue(wrote_tool_use, "test is vacuous — no tool_use was ever recorded")
        self.assertEqual(_orphan_ids(agent.conversation), [],
                         "closing the generator mid tool-loop orphaned a tool_use")


if __name__ == "__main__":
    unittest.main()
