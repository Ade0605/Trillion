"""
Personality persistence — fights tonal drift in long conversations.

Trillion has a warm, plain-spoken, brief "sharp colleague" voice on turn one, but
over many turns the model's own prior outputs out-weigh the cached personality
block at the top of context, and it slides toward generic-assistant mode
("Great question, let me help you with that"). The fix is positional, not
motivational:

1. A **voice cue** appended to the LAST user message in the API payload only
   (never stored) — it sits AFTER all prior assistant turns, where the model
   attends most strongly.
2. A **tonal checkpoint** in the uncached, per-turn system block — reinforcing
   from the other end of the context window.

The personality file (AGENT.md) carries the full voice spec; these two carry the
concrete examples and the reminder, positioned where the model actually attends.
"""
from __future__ import annotations

# Concrete one-liners of how Trillion should sound. Warm, brief, leads with the
# answer — a colleague who knows you, not a help desk. Kept in sync with AGENT.md.
VOICE_EXAMPLES = [
    "Three reminders — the 2:30 barbecue's the only urgent one.",
    "Done. Anything else?",
    "Nothing due today, you're clear.",
    "That'll spend an ElevenLabs credit — want me to?",
    "Short answer: yes. Longer one if you want it.",
    "Can't send that for you, but here's the draft to check.",
]

# Customer-service openers Trillion must never produce.
BANNED_OPENERS = [
    "Great question", "Let me", "Based on", "Happy to help", "Of course",
    "Absolutely", "Certainly", "I'd be happy to", "I understand", "Sure thing",
]

_CUE_EXAMPLES = " / ".join(f'"{e}"' for e in VOICE_EXAMPLES[:4])
_CUE_BANNED = ", ".join(f'"{b}"' for b in BANNED_OPENERS)

VOICE_CUE = (
    "[Voice check — you're Trillion, a sharp colleague, not a help desk. Lead "
    "with the answer; one or two sentences unless detail was asked. Plain and "
    "warm, no filler. Sound like: " + _CUE_EXAMPLES + ". Never open with " +
    _CUE_BANNED + ". Before sending: could a default chatbot have written this? "
    "If yes, cut the filler and lead with the answer. Warm and direct — never "
    "cold, curt, or robotic.]"
)

# Tighter reminder for the uncached, per-turn system block (~120 tokens).
TONAL_CHECKPOINT = (
    "\n## Tonal checkpoint\n"
    "Quick voice check before you send.\n"
    "(1) LENGTH. Longer than two sentences? Cut, unless the user asked for "
    "detail. Most replies fit in one.\n"
    "(2) VOICE. Opening with \"Great question\" / \"Let me\" / \"Based on\" / "
    "\"Happy to help\" / \"I understand\"? Stop and rewrite — lead with the "
    "answer. Could a default chatbot have written this line? If yes, make it "
    "sound like a person who knows the user."
)


def append_voice_cue(messages: list[dict]) -> list[dict]:
    """Append the voice cue to the last user-text message in the API payload.

    No-op for empty history, assistant-last messages, or block-list content
    (tool_result rounds — appending text to a block list breaks the
    tool_use ↔ tool_result pairing). Replaces the last dict with a new one, so
    when called on a shallow copy of stored history it never mutates the stored
    message objects. The cue must live in the API-bound copy ONLY — if it were
    stored, the model would see it dozens of times and start parroting its
    bracketed format.
    """
    if not messages:
        return messages
    last = messages[-1]
    if last.get("role") != "user":
        return messages
    content = last.get("content")
    if not isinstance(content, str):
        return messages
    messages[-1] = {**last, "content": f"{content}\n\n{VOICE_CUE}"}
    return messages
