"""
Per-turn model routing — answer short, simple turns on a fast model so the
voice loop's time-to-first-token roughly halves, while complex turns stay on
the stronger model.

Measured motivation: with everything already streamed, the dominant remaining
latency in a warm turn is the model's TTFB (~1.3s on the strong model). A quick
"what's the capital of France?" does not need that model — Haiku answers it in
roughly half the time and sounds identical for conversational turns.

Bias is toward the STRONG model when unsure: mis-routing a complex turn to the
fast model degrades an answer (bad), whereas keeping a trivial turn on the
strong model only costs a few hundred ms (mild). So the fast path fires only
when the turn is clearly short AND carries no complexity signal.

This is a word-list + threshold heuristic, not a model — tuning is a one-line
change. When a turn routes wrong, move a word between the sets below.
"""
from __future__ import annotations

import re

# Turns longer than this (in words) always take the strong model — length is a
# strong proxy for "this needs real reasoning."
_MAX_FAST_WORDS = 15

# Any of these anywhere in the turn forces the strong model. Kept lowercase;
# matched on word boundaries so "plan" does not fire inside "airplane".
_COMPLEX_TERMS = frozenset({
    "write", "code", "build", "debug", "refactor", "analyze", "analyse",
    "explain", "plan", "research", "compare", "summarize", "summarise",
    "draft", "design", "calculate", "review", "translate", "fix",
    "implement", "outline", "brainstorm", "diagnose", "optimize", "optimise",
    "rewrite", "investigate", "evaluate", "strategize", "architect",
})

_WORD = re.compile(r"[a-z0-9']+")
# More than one sentence-ender = a multi-part turn; treat as complex.
_SENTENCE_END = re.compile(r"[.!?]+")


def _looks_complex(text: str) -> bool:
    lowered = text.lower()
    if "`" in text or "```" in text:          # pasted code / snippets
        return True
    words = _WORD.findall(lowered)
    if len(words) > _MAX_FAST_WORDS:
        return True
    if _COMPLEX_TERMS.intersection(words):
        return True
    # Two or more real sentences is a compound request, not a quick turn.
    if len([s for s in _SENTENCE_END.split(text) if s.strip()]) > 1:
        return True
    return False


def pick_model(user_input: str, *, strong_model: str, fast_model: str) -> str:
    """Return the model id to use for this turn.

    Short, single-thought, keyword-clean turns route to `fast_model`;
    everything else (and anything ambiguous) stays on `strong_model`.
    """
    text = (user_input or "").strip()
    if not text:
        return strong_model
    return strong_model if _looks_complex(text) else fast_model


# ── tool gating ──────────────────────────────────────────────────────────────
# Sending all ~34 tool definitions costs ~2700 prompt tokens EVERY turn, which
# raises time-to-first-token even on a cache hit. Most conversational turns
# (greetings, thanks, factual questions) need no tool at all — for those we send
# no tools and the prefill roughly halves.
#
# Bias is HARD toward keeping tools: a turn that quietly needed a tool but got
# none just replies in text (mild, recoverable), whereas the speed win only
# matters on turns that were never going to call a tool. So tools are dropped
# ONLY for a short turn that contains none of the cue words below.
_TOOL_CUES = frozenset({
    # reminders / notes / calendar
    "remind", "reminder", "reminders", "todo", "task", "tasks", "due", "note",
    "notes", "calendar", "schedule", "meeting", "event", "events", "appointment",
    "agenda",
    # messaging / email
    "email", "mail", "send", "draft", "message", "reply", "compose", "forward",
    # web / search / apps
    "search", "google", "lookup", "website", "url", "link", "browse", "open",
    "close", "launch", "quit", "app", "application",
    # media / generation
    "play", "music", "song", "songs", "video", "image", "picture", "photo",
    "generate", "draw", "create", "make",
    # system control
    "shutdown", "restart", "reboot", "lock", "screenshot", "volume", "system",
    "status", "abort",
    # face / identity / sessions / design / agents
    "face", "enroll", "verify", "identity", "recognize", "rename", "session",
    "sessions", "history", "design", "screen", "mockup", "panel", "spawn",
    "agent", "delegate", "show", "list", "set", "add", "delete", "read",
})


def needs_tools(user_input: str, *, max_toolless_words: int = 15) -> bool:
    """Should this turn be sent WITH the full tool set?

    True (send tools) whenever any tool cue word appears, the turn is long
    enough to plausibly hide a request, or the input is empty/uncertain.
    False (drop tools) only for a short, cue-free turn — almost always pure
    conversation or a factual question.
    """
    text = (user_input or "").strip().lower()
    if not text:
        return True
    words = _WORD.findall(text)
    if set(words) & _TOOL_CUES:
        return True
    if len(words) > max_toolless_words:
        return True
    return False
