"""
Tests for per-turn model routing. Stdlib unittest.

    python -m unittest trillion.tests_model_router

The contract: short, single-thought, keyword-clean turns go to the fast model;
anything long, multi-sentence, code-bearing, or carrying a complexity keyword
stays on the strong model. Bias is toward the strong model when unsure.
"""
from __future__ import annotations

import unittest

from .model_router import pick_model

STRONG = "claude-sonnet-4-6"
FAST = "claude-haiku-4-5-20251001"


def route(text: str) -> str:
    return pick_model(text, strong_model=STRONG, fast_model=FAST)


class Routing(unittest.TestCase):
    def test_short_question_takes_fast(self):
        self.assertEqual(route("what's the capital of France?"), FAST)

    def test_greeting_takes_fast(self):
        self.assertEqual(route("hey, how are you?"), FAST)

    def test_short_command_takes_fast(self):
        self.assertEqual(route("what time is it"), FAST)

    def test_long_turn_takes_strong(self):
        long = "so here is the situation " + "and then " * 10 + "what do you think"
        self.assertEqual(route(long), STRONG)

    def test_complexity_keyword_takes_strong(self):
        self.assertEqual(route("write a haiku"), STRONG)
        self.assertEqual(route("debug this for me"), STRONG)
        self.assertEqual(route("explain recursion"), STRONG)

    def test_multi_sentence_takes_strong(self):
        self.assertEqual(route("The revenue is up. Should I hire?"), STRONG)

    def test_code_bearing_takes_strong(self):
        self.assertEqual(route("what does `map()` do"), STRONG)

    def test_empty_takes_strong(self):
        self.assertEqual(route(""), STRONG)
        self.assertEqual(route("   "), STRONG)

    def test_keyword_only_on_word_boundary(self):
        # "plan" must not fire inside "airplane"
        self.assertEqual(route("is that an airplane"), FAST)

    def test_disabled_when_models_equal(self):
        self.assertEqual(pick_model("write a novel", strong_model=STRONG, fast_model=STRONG), STRONG)
        self.assertEqual(pick_model("hi", strong_model=STRONG, fast_model=STRONG), STRONG)


if __name__ == "__main__":
    unittest.main()
