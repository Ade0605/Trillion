"""
netguard — refuse any address that points at the user's own machine or network,
and pin the connection to an IP that was actually checked.

Two attacks this stops:
- SSRF: a page tells the agent to open localhost, the router, or the cloud
  metadata address (169.254.169.254) that hands out credentials. Those are
  reachable from the user's machine but not from the public internet, so every
  resolved IP must be globally routable or the fetch is refused.
- DNS rebinding: an attacker's name resolves PUBLIC when we check and PRIVATE a
  moment later when we connect. We resolve once, check every answer, and hand
  the connection the exact checked IP — there is no second lookup to poison.

The resolver is injectable so tests can fake DNS without touching the network.
"""
from __future__ import annotations

import ipaddress
import socket

_CGNAT = ipaddress.ip_network("100.64.0.0/10")   # carrier-grade NAT (RFC 6598)


class NetError(ValueError):
    """An address that resolves somewhere non-public. Message is a plain reason."""


def is_public_ip(ip_str: str) -> bool:
    """True only for a globally routable public address.

    Unwraps IPv4-in-IPv6 first, then rejects loopback, private, link-local
    (incl. 169.254.169.254), CGNAT, multicast, reserved and unspecified.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast
            or ip.is_reserved or ip.is_unspecified):
        return False
    if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT:
        return False
    return bool(ip.is_global)        # the authoritative "is this routable" check


def _default_resolver(host: str) -> list[str]:
    """Resolve a host to every IP (A and AAAA) via the system resolver."""
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    # de-dup while keeping order stable for tests
    seen, out = set(), []
    for info in infos:
        ip = info[4][0]
        if ip not in seen:
            seen.add(ip)
            out.append(ip)
    return out


def resolve_public_ips(host: str, *, resolver=_default_resolver) -> list[str]:
    """Resolve `host` ONCE and return its IPs only if EVERY one is public.

    Raises NetError if the host doesn't resolve or any answer is non-public.
    The caller connects to one of the returned IPs — never re-resolving — so a
    rebinding resolver that later answers private cannot change the target.
    """
    host = (host or "").strip().lower()
    if not host:
        raise NetError("that address has no host")
    try:
        ips = resolver(host)
    except Exception:
        raise NetError("I couldn't look that address up")
    if not ips:
        raise NetError("that address didn't resolve to anything")
    for ip in ips:
        if not is_public_ip(ip):
            raise NetError("that address points to a private or local location, "
                           "so I won't open it")
    return ips
