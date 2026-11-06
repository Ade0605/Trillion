"""
Tests for Layer 2: the network guard (SSRF + DNS rebinding).

    python -m unittest trillion.web_reader.tests_netguard
"""
from __future__ import annotations

import unittest

from .netguard import is_public_ip, resolve_public_ips, NetError


class PublicCheck(unittest.TestCase):
    def test_non_public_ips_refused(self):
        for ip in ["127.0.0.1", "::1", "10.0.0.1", "172.16.5.4", "192.168.1.1",
                   "169.254.169.254", "100.64.0.1", "0.0.0.0", "::ffff:127.0.0.1",
                   "fe80::1", "fc00::1", "224.0.0.1"]:
            self.assertFalse(is_public_ip(ip), ip)

    def test_public_ips_allowed(self):
        for ip in ["1.1.1.1", "8.8.8.8", "93.184.216.34", "2606:4700:4700::1111"]:
            self.assertTrue(is_public_ip(ip), ip)

    def test_garbage_is_not_public(self):
        self.assertFalse(is_public_ip("not-an-ip"))
        self.assertFalse(is_public_ip(""))


def _fixed(mapping):
    """A fake resolver: host -> list of IPs."""
    return lambda host: mapping.get(host, [])


class ResolveGuard(unittest.TestCase):
    def test_hosts_pointing_private_refused(self):
        cases = {
            "localhost": ["127.0.0.1"],
            "router.local": ["192.168.1.1"],
            "metadata": ["169.254.169.254"],
            "six.local": ["::1"],
        }
        for host, ips in cases.items():
            with self.assertRaises(NetError, msg=host):
                resolve_public_ips(host, resolver=_fixed({host: ips}))

    def test_one_public_one_private_is_refused(self):
        r = _fixed({"mixed.example": ["93.184.216.34", "10.0.0.5"]})
        with self.assertRaises(NetError):
            resolve_public_ips("mixed.example", resolver=r)

    def test_all_public_returns_the_checked_ips(self):
        r = _fixed({"ok.example": ["93.184.216.34", "1.1.1.1"]})
        self.assertEqual(resolve_public_ips("ok.example", resolver=r),
                         ["93.184.216.34", "1.1.1.1"])

    def test_rebinding_resolver_cannot_reach_private(self):
        # Answers public on the FIRST call, private on the second. Because the
        # guard resolves exactly once and the caller connects to the returned
        # IP, the private answer is never reachable.
        calls = {"n": 0}
        def rebinder(host):
            calls["n"] += 1
            return ["93.184.216.34"] if calls["n"] == 1 else ["127.0.0.1"]
        checked = resolve_public_ips("evil.example", resolver=rebinder)
        self.assertEqual(checked, ["93.184.216.34"])   # the connect target
        self.assertEqual(calls["n"], 1)                # resolved once, not twice

    def test_empty_resolution_refused(self):
        with self.assertRaises(NetError):
            resolve_public_ips("nope.example", resolver=_fixed({}))


if __name__ == "__main__":
    unittest.main()
