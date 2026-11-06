"""
web_reader — a web-fetch capability a hostile page cannot turn against the user.

Built in layers; the protection lives in code, not the prompt:
  Layer 1 (here): canonical addresses + a per-conversation allowlist, so the
                  model opens only what the user gave or a page already linked —
                  it can never compose an address to hide data in.
"""
from __future__ import annotations

from .urls import normalize_url, url_key, extract_urls, UrlError, REFUSAL
from .allowlist import Allowlist

__all__ = ["normalize_url", "url_key", "extract_urls", "UrlError", "REFUSAL", "Allowlist"]
