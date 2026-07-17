"""
Tests locking in the sign-off detector. Stdlib unittest.

    python -m unittest trillion.tests_turn_taking

These pin the asymmetric behavior: clear goodbyes go silent; questions,
commands, and continuations always get a reply. When tuning the word lists,
add the phrase that misbehaved here first.
"""
from __future__ import annotations

import unittest

from .turn_taking import is_signoff


class SignoffEndsConversation(unittest.TestCase):
    """These SHOULD be answered with silence."""

    SIGNOFFS = [
        "thanks",
        "thank you",
        "thanks so much",
        "okay thanks",
        "ok thanks",
        "great, thanks",
        "cool",
        "great",
        "perfect",
        "cool cool",
        "sounds good",
        "will do",
        "got it",
        "makes sense",
        "right on",
        "bye",
        "goodbye",
        "cheers",
        "no worries",
        "that works",
        "awesome, thank you",
        "great, I'll send that",
        "alright, I'll handle it",
        "perfect, I'll take care of it",
    ]

    def test_signoffs_go_silent(self):
        for phrase in self.SIGNOFFS:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_signoff(phrase), f"expected silence for: {phrase!r}")


class SignoffGetsReply(unittest.TestCase):
    """These SHOULD get a normal reply (never swallowed)."""

    REPLIES = [
        # questions / requests
        "can you also send that email?",
        "how about tomorrow instead",
        "what about the other reminder",
        "one more thing",
        "thanks, but can you resend it?",
        "tell me more",
        "remind me at 5",
        "what's next",
        # commands (not self-commit) — the bug we found
        "great, send that email",
        "cool, add a reminder for 3pm",
        "perfect, schedule it for Monday",
        "ok, delete that note",
        # continuations — the other bug we found
        "great, the meeting went well",
        "okay, so the revenue is up",
        "cool, now the tricky part",
        "actually, one thing",
        # bare ambiguous acks alone are not enough
        "okay",
        "sure",
        "yeah",
        "alright",
        # look-alikes must not be read as self-commit / positive
        "well, that's interesting",
        "ill be there in a minute",
        # too long to be a bare goodbye
        "thanks for that, it really helped me understand the whole thing",
    ]

    def test_replies_are_not_swallowed(self):
        for phrase in self.REPLIES:
            with self.subTest(phrase=phrase):
                self.assertFalse(is_signoff(phrase), f"should reply to: {phrase!r}")


class FirstTurnGuard(unittest.TestCase):
    def test_first_utterance_never_swallowed(self):
        # Even a literal "thanks" as the very first thing said gets a reply.
        self.assertFalse(is_signoff("thanks", is_first_turn=True))
        self.assertFalse(is_signoff("bye", is_first_turn=True))

    def test_empty_is_not_a_signoff(self):
        self.assertFalse(is_signoff(""))
        self.assertFalse(is_signoff("   "))


if __name__ == "__main__":
    unittest.main()
