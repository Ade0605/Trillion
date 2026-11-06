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
from .netguard import resolve_public_ips, is_public_ip, NetError
from .fetch import fetch_url, FetchError, Page
from .fence import fence_page, defang
from .readstate import (ReadState, label_read_memory, MEMORY_READ_LABEL,
                        is_side_effect_after_read)
from .tool import ReaderContext, web_fetch, register_web_fetch

__all__ = [
    "normalize_url", "url_key", "extract_urls", "UrlError", "REFUSAL", "Allowlist",
    "resolve_public_ips", "is_public_ip", "NetError",
    "fetch_url", "FetchError", "Page",
    "fence_page", "defang", "ReadState", "label_read_memory", "MEMORY_READ_LABEL",
    "is_side_effect_after_read", "ReaderContext", "web_fetch", "register_web_fetch",
]
