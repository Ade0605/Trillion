"""
tool — the `web_fetch` tool, tying Layers 1-4 together, plus the per-conversation
context the agent owns.

The tool opens an address only if the conversation allowlist already holds it
(the user said it, or a page already read linked it). It fetches the spelling WE
stored, never the model's input, so a model that pads the query to smuggle data
simply won't match an allowed address. Output is fenced as untrusted, harvested
links join the allowlist, and the turn is marked as having read outside content.
"""
from __future__ import annotations

from .allowlist import Allowlist
from .readstate import ReadState
from .urls import REFUSAL, UrlError
from .netguard import NetError, resolve_public_ips
from .fetch import fetch_url, FetchError, _requests_transport
from .fence import fence_page


class ReaderContext:
    """Per-conversation allowlist + per-turn read state, shared with the agent."""

    def __init__(self) -> None:
        self.allow = Allowlist()
        self.read = ReadState()

    def start_turn(self, user_text: str) -> None:
        """Begin a user turn: allow what the user said, clear the read flag."""
        self.read.reset()
        self.allow.add_from_user_text(user_text)


def web_fetch(url: str, *, ctx: ReaderContext,
              resolve=resolve_public_ips, transport=_requests_transport) -> str:
    """Open an allowed address and return its text, fenced as untrusted."""
    if not ctx.allow.allows(url):
        return REFUSAL
    target = ctx.allow.canonical(url) or url        # our spelling, not the model's
    try:
        page = fetch_url(target, resolve=resolve, transport=transport)
    except (UrlError, NetError, FetchError) as e:
        return f"I couldn't open that — {e}."
    ctx.allow.add_from_links(page.links)            # its links become openable
    ctx.read.mark_read()                            # side-effects now need approval
    return fence_page(page)


_DESCRIPTION = (
    "Open a web page the user named, or a link on a page you already read, and "
    "return its text. You cannot open an address you made up — only ones the "
    "user gave or a page already linked. Pass the address exactly as given."
)
_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"url": {"type": "string",
                           "description": "The address to open, as the user said it."}},
    "required": ["url"],
}


def register_web_fetch(registry, ctx: ReaderContext) -> None:
    """Register web_fetch bound to this conversation's context."""
    registry.register(
        name="web_fetch",
        description=_DESCRIPTION,
        input_schema=_INPUT_SCHEMA,
        fn=lambda url: web_fetch(url, ctx=ctx),
    )
