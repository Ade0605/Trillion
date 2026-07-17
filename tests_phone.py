"""
Tests for the phone PWA server adapter. Stdlib unittest + Flask test client.

    python -m unittest tests_phone
"""
from __future__ import annotations

import os
import time
import unittest

from web_server import app
from trillion import phone


class TurnStoreTests(unittest.TestCase):
    def test_record_and_get(self):
        tid = phone.record_turn_text("hello there")
        self.assertEqual(phone.get_turn_text(tid), "hello there")

    def test_get_survives_repeated_reads(self):
        # iOS Safari GETs the audio source twice — the store must not evict on read.
        tid = phone.record_turn_text("twice")
        self.assertEqual(phone.get_turn_text(tid), "twice")
        self.assertEqual(phone.get_turn_text(tid), "twice")

    def test_missing_returns_none(self):
        self.assertIsNone(phone.get_turn_text("nope"))

    def test_expiry(self):
        tid = phone.record_turn_text("temp")
        phone._store[tid] = ("temp", time.monotonic() - 1)  # force-expire
        self.assertIsNone(phone.get_turn_text(tid))


class PhoneEndpointTests(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()
        # These verify open-endpoint / not-found behavior — pin no-token mode so
        # a TRILLION_TOKEN in .env doesn't turn a 404 into a 401.
        self._old = os.environ.pop("TRILLION_TOKEN", None)

    def tearDown(self):
        if self._old is not None:
            os.environ["TRILLION_TOKEN"] = self._old

    def test_shell_no_store(self):
        r = self.c.get("/phone")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Cache-Control"), "no-store")

    def test_manifest_and_sw_and_icon(self):
        self.assertEqual(self.c.get("/manifest.webmanifest").status_code, 200)
        self.assertEqual(self.c.get("/sw.js").status_code, 200)
        self.assertEqual(self.c.get("/phone-icon.svg").status_code, 200)

    def test_tts_missing_turn_is_404(self):
        self.assertEqual(self.c.get("/api/tts/doesnotexist").status_code, 404)

    def test_security_headers_present(self):
        r = self.c.get("/phone")
        self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("media-src 'self' blob: data:", r.headers.get("Content-Security-Policy", ""))


class AuthGatingTests(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()
        self._old = os.environ.get("TRILLION_TOKEN")
        os.environ["TRILLION_TOKEN"] = "testtoken1234567890"

    def tearDown(self):
        if self._old is None:
            os.environ.pop("TRILLION_TOKEN", None)
        else:
            os.environ["TRILLION_TOKEN"] = self._old

    def test_protected_route_requires_token(self):
        self.assertEqual(self.c.get("/api/security/status").status_code, 401)

    def test_token_via_query_param(self):
        # The <audio> element and WS can only pass ?token=
        r = self.c.get("/api/security/status?token=testtoken1234567890")
        self.assertEqual(r.status_code, 200)

    def test_shell_open_without_token(self):
        self.assertEqual(self.c.get("/phone").status_code, 200)

    def test_cross_origin_post_rejected(self):
        r = self.c.post("/reset", headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
