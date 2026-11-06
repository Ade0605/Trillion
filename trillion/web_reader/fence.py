"""
fence — Layer 4. Everything the reader returns is wrapped as untrusted web
content so the model treats it as information, never instructions. Any fence
marker hidden in the page is neutralised first, so a page can't "close" the
fence early and start speaking as the system.

Reuses the project's existing injection gate (which also flags known attack
phrases) and its SYSTEM_PROMPT_RULE, so the board and the reader share one rule.
"""
from __future__ import annotations

import re

from ..security.injection_gate import gate

# Any real or forged <untrusted...> / </untrusted...> tag in page text.
_MARKER = re.compile(r"<\s*/?\s*untrusted[^>]*>", re.I)


def defang(text: str) -> str:
    """Remove fence markers a page might use to break out of the wrapper."""
    return _MARKER.sub("[marker removed]", text or "")


def fence_page(page) -> str:
    """Render a fetched Page as a fenced, untrusted block the model may report
    on but must never obey. Links are listed after, marked as openable."""
    g = gate(defang(page.text), source="web_page")
    parts = [f"Web page: {page.title or page.url}", f"URL: {page.url}", "", g.to_prompt()]
    if page.links:
        parts.append("\nLinks on this page (you may ask to open any of these):")
        parts.extend(f"- {u}" for u in page.links[:40])
    return "\n".join(parts)
