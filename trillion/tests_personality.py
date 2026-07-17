"""
Structural tests for the personality-persistence layer.

    python -m unittest trillion.tests_personality

These prove the wiring: the cue rides the API payload only, never stored
history, skips tool_result rounds, and carries examples + banned openers +
guardrail. Whether Trillion actually *sounds* right is a live-conversation call.
"""
from __future__ import annotations

import unittest

from .personality import (
    append_voice_cue, VOICE_CUE, VOICE_EXAMPLES, BANNED_OPENERS, TONAL_CHECKPOINT,
)


class VoiceCueTests(unittest.TestCase):
    def test_cue_on_last_user_message(self):
        api = append_voice_cue([{"role": "user", "content": "what's due today?"}])
        self.assertIn(VOICE_CUE, api[-1]["content"])
        self.assertTrue(api[-1]["content"].startswith("what's due today?"))

    def test_cue_not_written_to_stored_history(self):
        stored = [{"role": "user", "content": "hi"}]
        append_voice_cue(list(stored))          # operate on a shallow copy
        self.assertEqual(stored[-1]["content"], "hi")  # original untouched

    def test_cue_lands_after_assistant_turns_only_on_last_user(self):
        hist = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
        ]
        api = append_voice_cue(list(hist))
        self.assertIn(VOICE_CUE, api[-1]["content"])
        self.assertNotIn(VOICE_CUE, api[0]["content"])

    def test_skips_block_list_content(self):
        # tool_result rounds carry a block list, not a string — must be a no-op.
        tool_round = [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "x", "content": "42"}]}]
        api = append_voice_cue([dict(tool_round[0])])
        self.assertIsInstance(api[-1]["content"], list)
        self.assertEqual(api[-1]["content"], tool_round[0]["content"])

    def test_noop_when_last_is_assistant(self):
        api = append_voice_cue([{"role": "assistant", "content": "done"}])
        self.assertNotIn(VOICE_CUE, api[-1]["content"])

    def test_cue_has_banned_openers_and_positive_direction(self):
        self.assertIn("Great question", VOICE_CUE)          # a banned opener
        self.assertIn("Let me", VOICE_CUE)
        self.assertIn("lead with the answer", VOICE_CUE.lower())  # positive direction

    def test_cue_embeds_voice_examples(self):
        self.assertTrue(any(ex in VOICE_CUE for ex in VOICE_EXAMPLES))

    def test_cue_has_cruelty_guardrail(self):
        self.assertIn("never", VOICE_CUE.lower())
        self.assertTrue("cold" in VOICE_CUE.lower() or "cruel" in VOICE_CUE.lower())


class PlacementTests(unittest.TestCase):
    def test_checkpoint_in_uncached_system_block_not_cached(self):
        from .agent import Agent
        blocks = Agent()._system_blocks()
        cached = blocks[0]
        uncached = blocks[-1]
        self.assertIn("cache_control", cached)              # personality is cached
        self.assertNotIn("Tonal checkpoint", cached["text"])  # cue/checkpoint not in cache
        self.assertNotIn("cache_control", uncached)          # checkpoint block is uncached
        self.assertIn("Tonal checkpoint", uncached["text"])

    def test_personality_examples_in_agent_md(self):
        from pathlib import Path
        md = (Path(__file__).parent.parent / "AGENT.md").read_text(encoding="utf-8")
        self.assertIn("Never sound like this", md)
        self.assertIn("Great question", md)


if __name__ == "__main__":
    unittest.main()
