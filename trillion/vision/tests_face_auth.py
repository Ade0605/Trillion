"""Tests for face enrollment/verification. Webcam and face_recognition calls
are mocked at _capture_encoding — only the storage/matching logic is real."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from trillion.vision import face_auth


class FakeRegistry:
    def __init__(self):
        self.registered = {}

    def register(self, name, description, input_schema, fn, requires_confirmation=False):
        self.registered[name] = {"fn": fn, "requires_confirmation": requires_confirmation}


class WithTempData(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._patcher = patch.object(face_auth, "_DATA", Path(self._tmpdir.name) / "encodings.json")
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmpdir.cleanup()


class EnrollFace(WithTempData):
    def test_blank_name_is_rejected(self):
        result = face_auth.enroll_face("   ")
        self.assertIn("Need a name", result)

    @patch("trillion.vision.face_auth._capture_encoding")
    def test_averages_samples_and_persists(self, mock_capture):
        mock_capture.side_effect = [
            (np.array([1.0, 1.0]), None),
            (np.array([3.0, 3.0]), None),
        ]
        result = face_auth.enroll_face("Bami", samples=2)
        self.assertIn("Enrolled 'Bami'", result)
        data = face_auth._load()
        self.assertIn("Bami", data)
        self.assertAlmostEqual(data["Bami"][0], 2.0)

    @patch("trillion.vision.face_auth._capture_encoding")
    def test_capture_failure_propagates_the_reason(self, mock_capture):
        mock_capture.return_value = (None, "No face detected — face the camera and try again.")
        result = face_auth.enroll_face("Bami")
        self.assertIn("No face detected", result)


class VerifyIdentity(WithTempData):
    @patch("trillion.vision.face_auth._capture_encoding")
    def test_no_one_enrolled(self, mock_capture):
        result = face_auth.verify_identity()
        self.assertIn("No one is enrolled", result)
        mock_capture.assert_not_called()  # no point opening the camera

    @patch("trillion.vision.face_auth._capture_encoding")
    def test_matches_closest_within_tolerance(self, mock_capture):
        face_auth._save({"Bami": [0.0, 0.0], "Stranger": [10.0, 10.0]})
        mock_capture.return_value = (np.array([0.1, 0.1]), None)
        result = face_auth.verify_identity()
        self.assertIn("Bami", result)
        self.assertIn("match", result.lower())

    @patch("trillion.vision.face_auth._capture_encoding")
    def test_rejects_match_outside_tolerance(self, mock_capture):
        face_auth._save({"Bami": [0.0, 0.0]})
        mock_capture.return_value = (np.array([5.0, 5.0]), None)
        result = face_auth.verify_identity(tolerance=0.5)
        self.assertIn("No match", result)


class ListAndForget(WithTempData):
    def test_list_empty(self):
        self.assertIn("No one is enrolled", face_auth.list_enrolled())

    def test_list_and_forget_roundtrip(self):
        face_auth._save({"Bami": [0.0], "Guest": [1.0]})
        listed = face_auth.list_enrolled()
        self.assertIn("Bami", listed)
        self.assertIn("Guest", listed)

        result = face_auth.forget_face("Guest")
        self.assertIn("Removed 'Guest'", result)
        self.assertNotIn("Guest", face_auth._load())

    def test_forget_unknown_name(self):
        result = face_auth.forget_face("Nobody")
        self.assertIn("isn't enrolled", result)


class Registration(unittest.TestCase):
    def test_registers_four_tools_with_correct_confirmation_flags(self):
        reg = FakeRegistry()
        face_auth.register_face_auth(reg)
        self.assertEqual(
            set(reg.registered),
            {"enroll_face", "verify_identity", "list_enrolled_faces", "forget_face"},
        )
        self.assertFalse(reg.registered["enroll_face"]["requires_confirmation"])
        self.assertFalse(reg.registered["verify_identity"]["requires_confirmation"])
        self.assertTrue(reg.registered["forget_face"]["requires_confirmation"])


if __name__ == "__main__":
    unittest.main()
