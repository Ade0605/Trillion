"""
urls — one canonical spelling for any address, and strict refusal of the shapes
an attacker hides data in. The reader never lets the model compose an address;
it only opens addresses that were already said or already linked, matched by the
canonical key here. The query string is kept and is part of the key, because the
query string is exactly where stolen data would be smuggled.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

MAX_URL = 2000

# A refusal the model can repeat to the user verbatim.
REFUSAL = ("I can only open addresses you give me, or links on a page I've "
           "already read.")


class UrlError(ValueError):
    """An address that can't be opened. Message is a short plain reason."""


_CONTROL_OR_SPACE = re.compile(r"[\x00-\x20\x7f]")
_HAS_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def normalize_url(raw: object) -> str:
    """Return the single canonical spelling of `raw`, or raise UrlError.

    https:// is added when no scheme is present; the host is lowercased and
    IDNA-encoded to ASCII; the #fragment is dropped; the path and query are
    kept. Refuses non-http(s) schemes, ports other than 80/443, embedded
    credentials, whitespace/control characters, and absurd length.
    """
    s = str(raw or "").strip()
    if not s:
        raise UrlError("no address given")
    if len(s) > MAX_URL:
        raise UrlError("that address is too long")
    if not _HAS_SCHEME.match(s):
        s = "https://" + s
    if _CONTROL_OR_SPACE.search(s):
        raise UrlError("that address has spaces or control characters")

    parts = urlsplit(s)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise UrlError("I can only open http and https addresses")
    if parts.username or parts.password:
        raise UrlError("that address has a username or password in it")

    host = parts.hostname
    if not host:
        raise UrlError("that address has no host")
    try:
        host = host.encode("idna").decode("ascii").lower()
    except Exception:
        host = host.lower()

    try:
        port = parts.port
    except ValueError:
        raise UrlError("that address has an invalid port")
    if port is not None and port not in (80, 443):
        raise UrlError("I can only open ports 80 and 443")

    path = parts.path or "/"
    # rebuild without the fragment and without an explicit default port
    return urlunsplit((scheme, host, path, parts.query, ""))


def url_key(normalized: str) -> str:
    """A match key: scheme-insensitive and trailing-slash-insensitive (so
    http/https and a trailing slash are the same address) but query-sensitive
    (a different query string is a DIFFERENT address and will not match)."""
    p = urlsplit(normalized)
    path = (p.path or "/").rstrip("/") or "/"
    key = (p.hostname or "").lower() + path
    if p.query:
        key += "?" + p.query
    return key


# full URLs, or bare ones like "example.com/pricing" (requires a real TLD)
_URL_RE = re.compile(
    r"https?://[^\s<>\"'\)]+"
    r"|(?:www\.)?(?:[a-z0-9][a-z0-9\-]*\.)+[a-z]{2,}(?:/[^\s<>\"'\)]*)?",
    re.I,
)
# how people say addresses aloud (speech-to-text): "example dot com slash x"
_SPOKEN = [
    (r"\s+dot\s+", "."), (r"\s+slash\s+", "/"), (r"\s+dash\s+", "-"),
    (r"\s+underscore\s+", "_"),
]
_TRAILING = ".,;:!?)]}>'\""


def extract_urls(text: object) -> list[str]:
    """Pull addresses out of something the user said/typed — full URLs, bare
    domains, and spoken forms. Returns canonical URLs, de-duplicated by key.
    Never raises: unparseable candidates are skipped."""
    raw = str(text or "")
    spoken = raw
    for pat, rep in _SPOKEN:
        spoken = re.sub(pat, rep, spoken, flags=re.I)

    found: list[str] = []
    seen: set[str] = set()
    for src in (raw, spoken):
        for m in _URL_RE.findall(src):
            candidate = m.rstrip(_TRAILING)
            try:
                norm = normalize_url(candidate)
            except UrlError:
                continue
            k = url_key(norm)
            if k not in seen:
                seen.add(k)
                found.append(norm)
    return found
