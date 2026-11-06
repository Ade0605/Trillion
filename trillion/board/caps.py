"""
caps — the hard limits the board enforces, in one place.

Character caps TRIM (never reject): an over-long title is clipped with an
ellipsis so a slightly chatty model still renders. Count caps REJECT the
overflow silently by slicing, so a 9-series chart draws its first 5 rather than
failing the whole board.

Tone is a WORD, never a colour — the page maps the word to a design token, so
the board stays one visual system no matter what the model sends.
"""
from __future__ import annotations

# Character caps (trim with an ellipsis past these).
TITLE = 80
LABEL = 60
VALUE = 40
TEXT = 400

# Count caps (slice past these).
MAX_WIDGETS = 12          # widgets on one board
MAX_SERIES = 5            # series in a chart
MAX_ROWS = 50             # rows in a table / items in a list
MAX_POINTS = 60           # points in one chart series

# Tone words — the ONLY colour language a block may carry.
TONES = ("good", "bad", "attention", "neutral")
DEFAULT_TONE = "neutral"


def clip(text: object, limit: int) -> str:
    """Coerce to a single-line string and trim to `limit` with an ellipsis.

    Never raises; collapses internal whitespace so a pasted blob stays tidy.
    """
    s = " ".join(str(text if text is not None else "").split())
    if len(s) <= limit:
        return s
    # Reserve one char for the ellipsis; strip a trailing space before it.
    return s[: max(0, limit - 1)].rstrip() + "…"


def tone_or_default(value: object) -> str:
    """Return a valid tone word, falling back to neutral for anything unknown."""
    v = str(value or "").strip().lower()
    return v if v in TONES else DEFAULT_TONE
