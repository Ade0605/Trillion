"""
design_guide — the board's design system, written down for contributors. The
drawn half is the style page (/board?view=widgets and ?view=blocks), which pulls
from the server's own samples so it can never drift from what the model produces.
"""
from __future__ import annotations

from .blocks import BLOCK_TYPES
from .widgets import WIDGET_TYPES, FIELD_HINTS


def design_guide() -> str:
    blocks = ", ".join(BLOCK_TYPES)
    widgets = "\n".join(f"- **{t}** — {FIELD_HINTS.get(t, '')}" for t in WIDGET_TYPES)
    return f"""# The board design system

The page can draw a small, closed set of **blocks** and nothing else, so the
design system is enforced by what exists, not by a style guide to remember.

## Blocks (the only things the page draws)
{blocks}

Every string is drawn as text; the page never runs HTML or code from the model.
Colour is never carried in a block — only a tone WORD (good, bad, attention,
neutral), which the page maps to a design token. Length is clipped, never
rejected; structure is strict.

## Widgets (what the model writes; the server expands to blocks)
{widgets}

Any widget may also carry `title` and `source`.

## Rules
- One job per card. A title says what it shows.
- Numbers carry their unit and, where it exists, a comparison.
- "Empty" is said plainly, never filled with invented data.
- The model names the source; the SERVER stamps the time.
- Emoji are stripped from model text (arrows and check marks are kept).

## Adding a widget
1. A recipe in `widgets.py` (`_r_<name>`) that returns raw blocks.
2. A one-line `FIELD_HINTS` entry (shown in the tool description).
3. A realistic sample in `samples.py` (`_RAW_WIDGETS`).
4. A test in `tests_widgets.py`.

The style page (`/board?view=widgets`) then draws it automatically, in light and
dark. If one card looks off beside the others, fix the recipe, not the model.
"""
