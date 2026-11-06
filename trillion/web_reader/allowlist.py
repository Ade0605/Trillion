"""
allowlist — the set of addresses the reader may open in ONE conversation.

An address earns its place in exactly two ways:
  a. it appeared in something the user said or typed, or
  b. it was a link on a page the reader already opened this conversation.

The model can never add to it by composing an address, so it can never route
the user's data to a server of its choosing. Matching is by `url_key`, so a
trailing slash or http/https is the same address, but a changed query string is
not.
"""
from __future__ import annotations

from .urls import normalize_url, url_key, extract_urls, UrlError


class Allowlist:
    """Per-conversation set of allowed addresses (keys → canonical url)."""

    def __init__(self) -> None:
        self._by_key: dict[str, str] = {}

    def _add(self, normalized: str) -> None:
        self._by_key.setdefault(url_key(normalized), normalized)

    def add_from_user_text(self, text: object) -> list[str]:
        """Allow every address the user said/typed. Returns what was added."""
        added = []
        for url in extract_urls(text):
            if url_key(url) not in self._by_key:
                added.append(url)
            self._add(url)
        return added

    def add_from_links(self, urls: list[str]) -> None:
        """Allow links harvested from a page the reader already opened."""
        for u in urls or []:
            try:
                self._add(normalize_url(u))
            except UrlError:
                continue

    def allows(self, raw: object) -> bool:
        try:
            return url_key(normalize_url(raw)) in self._by_key
        except UrlError:
            return False

    def canonical(self, raw: object) -> str | None:
        """The stored canonical form of an allowed address, else None.

        Returns the spelling WE stored (from the user/page), not the model's,
        so a model that pads the query to smuggle data simply won't match."""
        try:
            return self._by_key.get(url_key(normalize_url(raw)))
        except UrlError:
            return None

    def __len__(self) -> int:
        return len(self._by_key)
