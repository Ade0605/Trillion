"""
Living self-knowledge for Trillion.

The doc at ``context/self/trillion.md`` has hand-written narrative sections plus
AUTO blocks that are regenerated from the live codebase. This package parses the
doc, regenerates the AUTO blocks, and produces a slim summary that gets injected
into the agent's system prompt so Trillion's self-description stays grounded in
what the code actually contains.
"""
from .render import (
    DOC_PATH,
    build_summary,
    refresh_text,
    write_refreshed,
    get_self_summary,
    get_full_doc,
)

__all__ = [
    "DOC_PATH",
    "build_summary",
    "refresh_text",
    "write_refreshed",
    "get_self_summary",
    "get_full_doc",
]
