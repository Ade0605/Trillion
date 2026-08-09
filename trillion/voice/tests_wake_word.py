"""Tests for the wake-word loop's pure logic (silence detection).
The hardware capture loop itself isn't tested — same convention as
push_to_talk.py, which has no tests either (nothing meaningful to assert
about a live mic without an integration rig)."""
from __future__ import annotations

import unittest

import numpy as np

from trillion.voice.wake_word import is_silent, rms


class Rms(unittest.TestCase):
    def test_zero_signal_is_zero(self):
        self.assertEqual(rms(np.zeros(100, dtype="int16")), 0.0)

    def test_empty_array_is_zero(self):
        self.assertEqual(rms(np.array([], dtype="int16")), 0.0)

    def test_constant_signal_equals_its_magnitude(self):
        self.assertAlmostEqual(rms(np.full(100, 500, dtype="int16")), 500.0, places=3)


class IsSilent(unittest.TestCase):
    def test_quiet_room_is_silent(self):
        quiet = np.random.randint(-50, 50, 1280, dtype="int16")
        self.assertTrue(is_silent(quiet))

    def test_loud_speech_is_not_silent(self):
        loud = np.full(1280, 5000, dtype="int16")
        self.assertFalse(is_silent(loud))

    def test_custom_threshold_is_respected(self):
        mid = np.full(100, 400, dtype="int16")
        self.assertTrue(is_silent(mid, threshold=500))
        self.assertFalse(is_silent(mid, threshold=300))


if __name__ == "__main__":
    unittest.main()
