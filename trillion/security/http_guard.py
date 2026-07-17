"""
HTTP surface guard — bearer token + per-IP auth rate-limit.

Threats: public-surface attack on the agent's endpoint (brute-forcing the
token) and unauthenticated access to a public bind. Only engaged when
TRILLION_TOKEN is set; when it isn't, Trillion binds localhost and the machine
boundary is the auth boundary.

Rotation: set TRILLION_TOKEN (current) and optionally TRILLION_TOKEN_PREV during
an overlap window; both authenticate until PREV is cleared.
"""
from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict, deque

# Auth rate-limit knobs
_MAX_FAILS = 10      # N failures ...
_WINDOW = 300        # ... within W seconds ...
_LOCKOUT = 900       # ... locks the IP out for L seconds

_fails: dict[str, deque] = defaultdict(deque)
_locked_until: dict[str, float] = {}


def token_required() -> bool:
    return bool(os.environ.get("TRILLION_TOKEN", "").strip())


def _valid_tokens() -> list[str]:
    toks = [os.environ.get("TRILLION_TOKEN", ""), os.environ.get("TRILLION_TOKEN_PREV", "")]
    return [t for t in toks if t.strip()]


def check_token(header_value: str | None) -> bool:
    """Constant-time compare of a Bearer header against current/prev tokens."""
    if not header_value:
        return False
    provided = header_value[7:] if header_value.lower().startswith("bearer ") else header_value
    provided = provided.strip()
    ok = False
    for tok in _valid_tokens():
        # Compare against every token (no early return) to avoid timing leaks.
        if hmac.compare_digest(provided, tok):
            ok = True
    return ok


def check_rate(ip: str) -> tuple[bool, float]:
    """(allowed, retry_after_seconds). False while the IP is locked out."""
    now = time.monotonic()
    until = _locked_until.get(ip)
    if until and now < until:
        return False, round(until - now, 1)
    if until and now >= until:
        _locked_until.pop(ip, None)
        _fails[ip].clear()
    return True, 0.0


def record_fail(ip: str) -> None:
    now = time.monotonic()
    dq = _fails[ip]
    dq.append(now)
    while dq and now - dq[0] > _WINDOW:
        dq.popleft()
    if len(dq) >= _MAX_FAILS:
        _locked_until[ip] = now + _LOCKOUT


def check_origin(headers, host: str) -> bool:
    """CSRF defense: reject state-changing requests whose Origin is a different
    site. Absent Origin (native clients, curl, same-origin GETs) is allowed."""
    origin = headers.get("Origin")
    if not origin:
        return True
    try:
        from urllib.parse import urlparse
        o = urlparse(origin).netloc
    except Exception:
        return False
    if o == host:
        return True
    # tolerate localhost/127.0.0.1 interchange on the same port
    o_host, _, o_port = o.partition(":")
    h_host, _, h_port = host.partition(":")
    local = {"localhost", "127.0.0.1", "::1"}
    if o_host in local and h_host in local and o_port == h_port:
        return True
    return False


def client_ip(headers, remote_addr: str | None) -> str:
    """Prefer the real client IP behind a proxy; fall back to the socket peer."""
    for h in ("CF-Connecting-IP", "X-Real-IP", "X-Forwarded-For"):
        v = headers.get(h)
        if v:
            return v.split(",")[0].strip()
    return remote_addr or "unknown"
