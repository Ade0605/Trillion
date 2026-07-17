"""
Shallow input sanitization for user-supplied role descriptions.

Not a defense against a determined attacker — it nudges sloppy/hostile input
into a safe shape before it flows into LLM prompts and the spec markdown. The
deeper guarantee (the spawned agent's system prompt paraphrases rather than
quotes user input verbatim) is enforced by the prompt-generator meta-prompt.
"""
from __future__ import annotations

import re

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INJECTION = re.compile(
    r"(ignore\s+(?:(?:all|the|previous|prior|above)\s+){1,3}(?:instructions|rules|prompts))"
    r"|((^|\n)\s*system\s*:)|(<\|?system\|?>)|(\[SYSTEM\])"
    r"|(disregard\s+(?:(?:all|the|previous|prior)\s+){1,3}(?:instructions|rules))"
    r"|(new\s+(instructions|task|prompt)\s*:)",
    re.IGNORECASE,
)


class UnsafeInputError(ValueError):
    pass


def sanitize(text: str, *, max_len: int = 2000) -> str:
    """Strip control chars, collapse whitespace, cap length. Raises
    UnsafeInputError if it contains overt prompt-injection patterns."""
    text = (text or "").strip()
    if not text:
        return ""
    text = _CONTROL.sub("", text)
    if _INJECTION.search(text):
        raise UnsafeInputError("role description contains prompt-injection patterns")
    text = re.sub(r"[ \t]+", " ", text)
    return text[:max_len]
