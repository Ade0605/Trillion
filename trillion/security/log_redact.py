"""
Log redaction — mask secret-shaped strings before they hit the audit log.

Threat: account/key compromise via a leaked log line (stack trace, journal,
screenshot, third-party log shipper). The audit log records tool inputs and
results verbatim; a web page fetched by web_search or an error string could
carry a token, an email, or a card number straight into logs/audit.log.

`mask()` masks; `redact()` masks then truncates. They're kept separate so the
truncation length is a caller knob independent of the masking.
"""
from __future__ import annotations

import re

# (pattern, replacement) applied in order. Ordered so specific shapes are
# masked before broad ones (e.g. provider keys before generic hex).
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Bearer / Authorization headers
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)\S+"), r"\1<redacted>"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"), "Bearer <redacted>"),
    # Provider API keys
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"), "sk-ant-<redacted>"),
    (re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{12,}"), "sk_<redacted>"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "sk-<redacted>"),
    (re.compile(r"sk_[A-Za-z0-9]{24,}"), "sk_<redacted>"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "gh_<redacted>"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "xox-<redacted>"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA<redacted>"),
    # JWT: three base64url segments
    (re.compile(r"eyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}"), "<jwt-redacted>"),
    # Connection-string password:  scheme://user:pass@host  ->  scheme://user:<redacted>@host
    (re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://[^:/\s@]+):([^@/\s]+)@"), r"\1:<redacted>@"),
    # Long hex secrets (Deepgram-style 40-hex keys, generic 32+ hex)
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "<hex-redacted>"),
    # Credit-card-shaped numbers — keep last 4
    (re.compile(r"\b(?:\d[ -]?){12}(\d{4})\b"), r"****-****-****-\1"),
]

# Email: keep first char of local part + full domain
_EMAIL = re.compile(r"\b([A-Za-z0-9])[A-Za-z0-9._%+\-]*(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")


def mask(text: str) -> str:
    """Mask secret / high-precision shapes anywhere in ``text``. No truncation."""
    if not text:
        return text
    out = text
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    out = _EMAIL.sub(lambda m: f"{m.group(1)}***{m.group(2)}", out)
    return out


def redact(text: str, max_len: int = 500) -> str:
    """Mask, then truncate to ``max_len``. Masking happens first so a secret is
    never left half-shown by the cut."""
    masked = mask(text or "")
    if max_len is not None and len(masked) > max_len:
        return masked[:max_len] + "…"
    return masked
