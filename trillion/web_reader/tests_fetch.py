"""
Tests for Layer 3: safe fetch + HTML→text + link harvest. Transport and
resolver are injected, so nothing touches the real network.

    python -m unittest trillion.web_reader.tests_fetch
"""
from __future__ import annotations

import unittest

from .fetch import fetch_url, Resp, FetchError, MAX_TEXT
from .netguard import resolve_public_ips, NetError
from .html_text import html_to_text


def resolver(mapping):
    """A resolve(host) that runs the real public-IP guard over a fake DNS map."""
    def inner(host):
        return resolve_public_ips(host, resolver=lambda h: mapping.get(h, []))
    return inner


PUBLIC = {"example.com": ["93.184.216.34"], "private.example": ["10.0.0.1"]}


class HtmlToText(unittest.TestCase):
    def test_scripts_and_styles_never_appear(self):
        html = ("<head><title>Roses</title><style>.x{color:red}</style></head>"
                "<body><script>steal()</script><p>Plant in autumn.</p></body>")
        title, text, _ = html_to_text(html, "https://example.com/")
        self.assertEqual(title, "Roses")
        self.assertIn("Plant in autumn.", text)
        self.assertNotIn("steal()", text)
        self.assertNotIn("color:red", text)

    def test_relative_links_become_full_addresses(self):
        html = '<a href="/next">n</a><a href="https://other.example/x">o</a>'
        _, _, links = html_to_text(html, "https://example.com/dir/")
        self.assertIn("https://example.com/next", links)
        self.assertIn("https://other.example/x", links)


class Fetch(unittest.TestCase):
    def test_redirect_to_private_is_refused(self):
        def t(url, host, ip):
            return Resp(302, {"Location": "http://private.example/"})
        with self.assertRaises(NetError):
            fetch_url("https://example.com/", resolve=resolver(PUBLIC), transport=t)

    def test_redirect_loop_stops_at_five(self):
        def t(url, host, ip):
            return Resp(302, {"Location": "/a"})
        with self.assertRaises(FetchError) as e:
            fetch_url("https://example.com/", resolve=resolver(PUBLIC), transport=t)
        self.assertIn("too many times", str(e.exception))

    def test_oversized_refused(self):
        def t(url, host, ip):
            return Resp(200, {"Content-Type": "text/html", "Content-Length": "9999999999"}, b"x")
        with self.assertRaises(FetchError):
            fetch_url("https://example.com/", resolve=resolver(PUBLIC), transport=t)

    def test_binary_refused(self):
        def t(url, host, ip):
            return Resp(200, {"Content-Type": "image/png"}, b"\x89PNG\r\n")
        with self.assertRaises(FetchError):
            fetch_url("https://example.com/", resolve=resolver(PUBLIC), transport=t)

    def test_good_page_returns_text_and_links(self):
        html = b"<title>T</title><p>Hello world</p><a href='/more'>m</a>"
        def t(url, host, ip):
            return Resp(200, {"Content-Type": "text/html"}, html)
        page = fetch_url("https://example.com/", resolve=resolver(PUBLIC), transport=t)
        self.assertEqual(page.title, "T")
        self.assertIn("Hello world", page.text)
        self.assertIn("https://example.com/more", page.links)

    def test_text_capped(self):
        big = ("word " * 5000).encode()        # ~25k chars
        def t(url, host, ip):
            return Resp(200, {"Content-Type": "text/plain"}, big)
        page = fetch_url("https://example.com/", resolve=resolver(PUBLIC), transport=t)
        self.assertLessEqual(len(page.text), MAX_TEXT + 1)


if __name__ == "__main__":
    unittest.main()
