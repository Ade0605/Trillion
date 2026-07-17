"""
Turn-taking: decide when Trillion should stay silent instead of taking the last
word. Runs on the raw transcript BEFORE any model call, so a goodbye costs
nothing — no tokens, no round trip.

Design bias (the failure modes are not symmetric): staying silent when the user
wanted a reply reads as broken, while replying to a borderline goodbye is only
mildly chatty. So every rule here leans toward *replying* when unsure.

Everything is driven by the word lists below — tuning is a one-line change. When
a real goodbye slips through (or it goes quiet when it shouldn't have), move the
phrase into the right bucket and add a test.
"""
from __future__ import annotations

import re

# Clear farewells / acknowledgements that end a conversation. May appear in a
# slightly longer (but still short) utterance.
STRONG_SIGNOFFS = (
    "bye", "goodbye", "good bye", "see you", "see ya", "talk later", "later",
    "cheers", "thanks", "thank you", "thx", "ty", "will do", "sounds good",
    "sound good", "got it", "understood", "noted", "makes sense", "that works",
    "right on", "appreciate it", "much appreciated", "no worries", "no problem",
    "all good", "we're good", "that's all", "thats all", "that's it", "thats it",
    "good night", "goodnight", "take care",
)

# Positive words that only end the conversation when the utterance is VERY short.
# "great, the meeting went well" is a continuation, not a goodbye.
CLOSING_POSITIVES = (
    "great", "cool", "perfect", "awesome", "sweet", "nice", "gotcha",
    "excellent", "brilliant", "fantastic", "lovely", "wonderful",
)

# Bare acknowledgements too ambiguous to end on their own. They only count when a
# STRONG signoff is also present ("okay thanks"), never alone ("okay").
AMBIGUOUS_ACKS = (
    "ok", "okay", "kay", "yes", "yeah", "yep", "yup", "sure", "right",
    "alright", "alrighty", "fine", "mhm", "uh huh",
)

# The user committing to do it themselves — "great, I'll send that" is a signoff,
# whereas "great, send that email" is a command. Apostrophe forms only, so we
# don't confuse "ill" with "I'll" or "well" with "we'll".
SELF_COMMIT = (
    "i'll", "i will", "we'll", "we will", "i'm going to", "i am going to",
    "i'll handle", "i'll take care", "i'll do", "i've got it", "i got it",
)

# Outward commands: if present without a self-commit, the user wants something
# done → reply. ("do" is deliberately excluded so "will do" stays a signoff.)
COMMAND_VERBS = frozenset((
    "send", "add", "remove", "delete", "set", "schedule", "remind", "search",
    "find", "draft", "write", "create", "update", "cancel", "call", "email",
    "text", "play", "open", "check", "make", "book", "order", "buy", "list",
    "save", "move", "change", "start", "stop", "pull", "fetch", "look",
))

# Question words that signal the user wants information back.
QUESTION_WORDS = frozenset((
    "what", "whats", "why", "when", "where", "who", "which", "how", "whose",
    "whom",
))

# Multi-word requests that mean "reply normally".
REQUEST_PHRASES = (
    "can you", "could you", "would you", "will you", "can we", "could we",
    "how about", "what about", "one more", "tell me", "show me", "give me",
    "i need", "i want", "i'd like", "help me", "let me know", "what's",
    "how do", "how does", "remind me",
)

# Words that mean the user is still going, not wrapping up.
CONTINUATION_WORDS = frozenset(("actually", "wait", "hold on", "also", "plus", "however"))

_MAX_WORDS = 6          # nothing longer than this is a signoff
_MAX_WEAK_WORDS = 3     # closing positives only end very short utterances


def _words(text: str) -> list[str]:
    """Lowercased word tokens, apostrophes kept ('i'll' stays one token)."""
    return re.findall(r"[a-z']+", text.lower())


def is_signoff(text: str, is_first_turn: bool = False) -> bool:
    """
    True if ``text`` is a conversational sign-off that Trillion should answer
    with silence. Conservative: returns False whenever anything suggests the
    user still wants a reply.
    """
    # Never let the very first thing said be swallowed as a goodbye.
    if is_first_turn:
        return False

    raw = text.strip()
    if not raw:
        return False

    words = _words(raw)
    if not words:
        return False
    n = len(words)

    # Long utterances are almost never bare goodbyes.
    if n > _MAX_WORDS:
        return False

    # --- Vetoes: any sign the user wants something back → reply ---
    if "?" in raw:
        return False

    padded = " " + " ".join(words) + " "
    wordset = set(words)

    if any(f" {p} " in padded for p in REQUEST_PHRASES):
        return False
    if wordset & QUESTION_WORDS:
        return False
    if wordset & CONTINUATION_WORDS or any(p in padded for p in (" hold on ",)):
        return False

    has_self_commit = any(p in padded for p in SELF_COMMIT)
    if not has_self_commit and (wordset & COMMAND_VERBS):
        return False

    # --- Positive evidence of a sign-off (all vetoes already passed) ---
    strong = any(f" {p} " in padded for p in STRONG_SIGNOFFS)
    if strong:
        return True

    # User committing to do it themselves is a sign-off.
    if has_self_commit:
        return True

    # A bare closing positive ends only very short utterances.
    if wordset & set(CLOSING_POSITIVES):
        return n <= _MAX_WEAK_WORDS

    # AMBIGUOUS_ACKS alone are never enough (needed a strong signoff, handled above).
    return False
