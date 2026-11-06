"""
Tests for Layer 1: address normalization + the per-conversation allowlist.

    python -m unittest trillion.web_reader.tests_urls
"""
from __future__ import annotations

import unittest

from .urls import normalize_url, url_key, extract_urls, UrlError
from .allowlist import Allowlist


class Normalize(unittest.TestCase):
    def test_table_of_good_addresses(self):
        cases = {
            "example.com": "https://example.com/",
            "http://Example.COM": "http://example.com/",
            "https://example.com/a/b?q=1#frag": "https://example.com/a/b?q=1",
            "example.com:443/x": "https://example.com/x",
            "  https://example.com/pricing  ": "https://example.com/pricing",
        }
        for raw, want in cases.items():
            self.assertEqual(normalize_url(raw), want, raw)

    def test_bad_addresses_refused(self):
        bad = [
            "ftp://example.com",            # scheme
            "http://example.com:8080/",     # port
            "https://user:pass@example.com",  # credentials
            "https://exa mple.com",         # space
            "javascript:alert(1)",          # scheme
            "https://" + "a" * 3000,        # length
        ]
        for raw in bad:
            with self.assertRaises(UrlError, msg=raw):
                normalize_url(raw)

    def test_two_spellings_match(self):
        # trailing slash and http/https are the same address
        self.assertEqual(url_key(normalize_url("http://example.com/a/")),
                         url_key(normalize_url("https://example.com/a")))

    def test_different_query_does_not_match(self):
        self.assertNotEqual(url_key(normalize_url("https://example.com/a")),
                            url_key(normalize_url("https://example.com/a?d=secret")))


class Extract(unittest.TestCase):
    def test_full_and_bare(self):
        urls = extract_urls("see https://example.com/pricing and example.org/docs")
        self.assertIn("https://example.com/pricing", urls)
        self.assertIn("https://example.org/docs", urls)

    def test_spoken_form(self):
        urls = extract_urls("go to example dot com slash pricing")
        self.assertIn("https://example.com/pricing", urls)

    def test_plain_words_are_not_urls(self):
        self.assertEqual(extract_urls("hello there, how are you"), [])


class AllowlistRules(unittest.TestCase):
    def test_address_i_said_is_allowed(self):
        a = Allowlist()
        a.add_from_user_text("please read https://example.com/post")
        self.assertTrue(a.allows("https://example.com/post"))
        self.assertTrue(a.allows("http://example.com/post/"))   # same address

    def test_link_from_read_page_is_allowed(self):
        a = Allowlist()
        a.add_from_links(["https://example.com/next", "news.example.com/story"])
        self.assertTrue(a.allows("https://example.com/next"))
        self.assertTrue(a.allows("https://news.example.com/story"))

    def test_address_only_in_page_text_is_refused(self):
        # page TEXT is never a source — only user text and page LINKS are.
        a = Allowlist()
        a.add_from_links(["https://example.com/a"])            # the links
        # an address that merely appeared in the article body was never added:
        self.assertFalse(a.allows("https://evil.example/collect"))

    def test_same_address_with_extra_query_is_refused(self):
        a = Allowlist()
        a.add_from_user_text("read https://example.com/p")
        self.assertTrue(a.allows("https://example.com/p"))
        self.assertFalse(a.allows("https://example.com/p?d=my-secrets"))

    def test_canonical_returns_our_spelling_not_the_models(self):
        a = Allowlist()
        a.add_from_user_text("https://example.com/p")
        self.assertEqual(a.canonical("http://example.com/p/"), "https://example.com/p")


if __name__ == "__main__":
    unittest.main()
