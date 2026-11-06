"""
fetch — Layer 3. Retrieve a page safely and hand back readable text + links.

Every address, and every redirect target, goes back through Layer 1's
normaliser and Layer 2's network guard before a socket is opened. The real
transport pins the connection to the exact IP that was checked (so DNS can't be
re-answered between check and connect) while TLS still verifies the certificate
against the hostname. Caps: 5 redirects, 15s, 2 MB, text-like content only, and
12,000 characters of text so one page can't flood the model.
"""
from __future__ import annotations

import contextlib
import socket
import threading
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from .urls import normalize_url, UrlError
from .netguard import resolve_public_ips, NetError

MAX_REDIRECTS = 5
TIMEOUT = 15
MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 12_000
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_TEXT_TYPES = {"text/html", "application/xhtml+xml", "text/plain",
               "text/markdown", "application/json"}

# Only one web fetch resolves+connects at a time: the real transport pins DNS
# process-wide for the moment of connection, so fetches must not overlap.
_FETCH_LOCK = threading.Lock()


class FetchError(ValueError):
    """A page that couldn't be read safely. Message is a plain reason."""


@dataclass
class Resp:
    """A minimal response the renderer understands (real or faked in tests)."""
    status: int
    headers: dict = field(default_factory=dict)
    body: bytes = b""

    def header(self, name: str) -> str:
        n = name.lower()
        for k, v in self.headers.items():
            if k.lower() == n:
                return v
        return ""


@dataclass
class Page:
    url: str
    title: str
    text: str
    links: list[str]


# ── the real, pinned transport ────────────────────────────────────────────────
@contextlib.contextmanager
def _pinned_dns(host: str, ip: str):
    """Within this block, resolving `host` returns the pre-checked `ip`, and any
    other hostname lookup is refused. Restores the resolver on exit."""
    real = socket.getaddrinfo

    def fake(*args, **kwargs):
        # getaddrinfo(host, port, ...) — host may be positional or keyword.
        args = list(args)
        h = args[0] if args else kwargs.get("host")
        if h != host:
            raise socket.gaierror(f"blocked unexpected lookup: {h}")
        if args:
            args[0] = ip
        else:
            kwargs = {**kwargs, "host": ip}
        return real(*args, **kwargs)

    socket.getaddrinfo = fake
    try:
        yield
    finally:
        socket.getaddrinfo = real


def _requests_transport(url: str, host: str, ip: str) -> Resp:
    import requests
    with _FETCH_LOCK, _pinned_dns(host, ip):
        r = requests.get(url, allow_redirects=False, stream=True, timeout=TIMEOUT,
                         verify=True, headers={"User-Agent": "TrillionWebReader/1.0",
                                               "Accept": "text/html,text/plain,application/json"})
        try:
            if r.status_code in _REDIRECT_CODES:
                return Resp(r.status_code, dict(r.headers), b"")
            body = bytearray()
            for chunk in r.iter_content(8192):
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    break
            return Resp(r.status_code, dict(r.headers), bytes(body))
        finally:
            r.close()


# ── orchestrator ──────────────────────────────────────────────────────────────
def fetch_url(url: str, *, resolve=resolve_public_ips, transport=_requests_transport) -> Page:
    """Fetch `url` safely and return a Page(url, title, text, links).

    `resolve` and `transport` are injectable so tests drive redirects, sizes and
    content types without touching the network.
    """
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        try:
            n = normalize_url(current)
        except UrlError as e:
            raise FetchError(str(e)) from e
        host = urlsplit(n).hostname or ""
        ips = resolve(host)                       # NetError if non-public
        resp = transport(n, host, ips[0])

        if resp.status in _REDIRECT_CODES:
            loc = resp.header("location")
            if not loc:
                raise FetchError("that page redirected without saying where")
            current = urljoin(n, loc)             # re-checked at the top of the loop
            continue
        if resp.status >= 400:
            raise FetchError(f"that page returned an error ({resp.status})")
        return _render(n, resp)

    raise FetchError("that page redirected too many times")


def _render(url: str, resp: Resp) -> Page:
    ctype = resp.header("content-type").split(";")[0].strip().lower()
    if ctype and ctype not in _TEXT_TYPES:
        raise FetchError("I can only read web pages and text, not that kind of file")
    declared = resp.header("content-length")
    if declared.isdigit() and int(declared) > MAX_BYTES:
        raise FetchError("that page is too large to read")
    if len(resp.body) > MAX_BYTES:
        raise FetchError("that page is too large to read")

    text = resp.body.decode("utf-8", "replace")
    if ctype in ("text/html", "application/xhtml+xml") or (not ctype and "<" in text[:200]):
        from .html_text import html_to_text
        title, body, links = html_to_text(text, url)
    else:
        title, body, links = "", text, []

    if len(body) > MAX_TEXT:
        body = body[:MAX_TEXT].rstrip() + "…"
    return Page(url=url, title=title[:200], text=body, links=links)
