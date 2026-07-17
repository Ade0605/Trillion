"""
Render the self-knowledge doc and derive the slim summary for the system prompt.

- ``refresh_text`` / ``write_refreshed`` regenerate the AUTO blocks from the live
  codebase, leaving hand-written sections untouched.
- ``build_summary`` produces a compact (~roughly 400-token) block — identity +
  core principles + capability names + integrations — meant to sit in every
  turn's system prompt. ``get_self_summary`` is a cached accessor for that.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import parser
from .generators import default_generators, live_registry, load_config

_ROOT = Path(__file__).parent.parent.parent
DOC_PATH = _ROOT / "context" / "self" / "trillion.md"


# --------------------------------------------------------------------------- #
# Full-doc refresh
# --------------------------------------------------------------------------- #

def refresh_text(text: str | None = None) -> str:
    """Return the doc with all AUTO blocks regenerated from live sources."""
    if text is None:
        text = DOC_PATH.read_text(encoding="utf-8")
    return parser.render(text, default_generators())


def write_refreshed() -> bool:
    """Refresh the doc on disk. Returns True if the file changed."""
    original = DOC_PATH.read_text(encoding="utf-8")
    refreshed = refresh_text(original)
    if refreshed != original:
        DOC_PATH.write_text(refreshed, encoding="utf-8", newline="")
        return True
    return False


# --------------------------------------------------------------------------- #
# Slim summary for the system prompt
# --------------------------------------------------------------------------- #

def _section_body(doc: str, heading: str) -> str:
    """Return the text under a ``## heading`` up to the next ``## ``."""
    pattern = re.compile(
        r"^##\s+" + re.escape(heading) + r"\s*$(.*?)(?=^##\s|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pattern.search(doc)
    return m.group(1).strip() if m else ""


def _first_paragraph(text: str) -> str:
    for block in text.split("\n\n"):
        block = block.strip()
        if block and not block.startswith(">"):
            return " ".join(block.split())
    return ""


def build_summary(doc: str | None = None) -> str:
    """
    A compact, accurate self-description for the system prompt: who Trillion is,
    the rules it must not break, the exact tools it has right now, and the wired
    integrations. Capability names come straight from the live registry so this
    can never claim a tool that doesn't exist.
    """
    if doc is None:
        doc = DOC_PATH.read_text(encoding="utf-8")

    identity = _first_paragraph(_section_body(doc, "Identity"))
    principles = _section_body(doc, "Core principles")

    try:
        tools = sorted(t.name for t in live_registry()._tools.values())
        tool_line = ", ".join(tools) if tools else "(none registered)"
    except Exception:
        tool_line = "(tool registry unavailable)"

    try:
        cfg = load_config()
        voice_id = cfg.get("elevenlabs_voice_id", "unknown")
    except Exception:
        voice_id = "unknown"

    parts = [
        "### About yourself (auto-generated from your live code — trust this over any assumption)",
        identity,
        "",
        "Rules you must not break:",
        principles,
        "",
        f"Tools you have right now: {tool_line}.",
        "",
        "Integrations wired right now: Anthropic (your brain), Deepgram "
        "(speech-to-text), and ElevenLabs (text-to-speech, voice "
        f"`{voice_id}`). You speak by default through the browser and the native "
        "app. If asked what you can do or whether you can talk, answer from this "
        "list — never invent a capability that isn't here, and never deny one "
        "that is. You cannot inspect your own live config, so for 'is my voice "
        "working right now?' defer to the page's voice banner and the user.",
    ]
    return "\n".join(parts).strip()


# --------------------------------------------------------------------------- #
# Cached accessor used by the agent at runtime
# --------------------------------------------------------------------------- #

_cached_summary: str | None = None


def get_self_summary(refresh: bool = False) -> str:
    """Cached slim summary. Cheap enough to inject on every turn."""
    global _cached_summary
    if _cached_summary is None or refresh:
        try:
            _cached_summary = build_summary()
        except Exception:
            _cached_summary = ""
    return _cached_summary


def get_full_doc() -> str:
    """The whole rendered doc, for ``mode: full``. Empty string if unreadable."""
    try:
        return DOC_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
