"""Tests for the system/application control tool. Stdlib unittest + mock."""
from __future__ import annotations

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from trillion.tools import system_control as sc


class FakeRegistry:
    def __init__(self):
        self.registered = {}

    def register(self, name, description, input_schema, fn, requires_confirmation=False):
        self.registered[name] = {
            "description": description,
            "schema": input_schema,
            "fn": fn,
            "requires_confirmation": requires_confirmation,
        }


class OpenApplication(unittest.TestCase):
    @patch("os.startfile")
    def test_known_app_opens(self, mock_start):
        result = sc.open_application("notepad")
        mock_start.assert_called_once_with("notepad.exe")
        self.assertIn("Opened", result)

    @patch("os.startfile")
    def test_case_and_whitespace_insensitive(self, mock_start):
        sc.open_application("  Notepad  ")
        mock_start.assert_called_once_with("notepad.exe")

    @patch("os.startfile")
    def test_unknown_app_does_not_call_startfile(self, mock_start):
        result = sc.open_application("some-random-exe")
        mock_start.assert_not_called()
        self.assertIn("isn't in the list", result)

    @patch("os.startfile", side_effect=OSError("boom"))
    def test_startfile_error_is_reported_not_raised(self, mock_start):
        result = sc.open_application("notepad")
        self.assertIn("Couldn't open", result)

    @patch("sys.platform", "linux")
    def test_non_windows_is_rejected(self):
        result = sc.open_application("notepad")
        self.assertIn("only supported on Windows", result)


class CloseApplication(unittest.TestCase):
    @patch("trillion.tools.system_control.subprocess.run")
    def test_known_closeable_app_calls_taskkill_with_minimal_env(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = sc.close_application("notepad")
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0], ["taskkill", "/IM", "notepad.exe", "/F"])
        # Minimal env: no secrets leak through to the killed process's launch.
        self.assertNotIn("ANTHROPIC_API_KEY", kwargs["env"])
        self.assertIn("Closed", result)

    @patch("trillion.tools.system_control.subprocess.run")
    def test_non_closeable_app_does_not_spawn_subprocess(self, mock_run):
        result = sc.close_application("explorer")
        mock_run.assert_not_called()
        self.assertIn("can't be closed", result)

    @patch("trillion.tools.system_control.subprocess.run")
    def test_unknown_app_does_not_spawn_subprocess(self, mock_run):
        result = sc.close_application("some-random-exe")
        mock_run.assert_not_called()
        self.assertIn("isn't in the list", result)

    @patch("trillion.tools.system_control.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="taskkill", timeout=10))
    def test_timeout_is_reported_not_raised(self, mock_run):
        result = sc.close_application("notepad")
        self.assertIn("Couldn't close", result)


class LockScreen(unittest.TestCase):
    @patch("ctypes.windll", create=True)
    def test_calls_lock_work_station(self, mock_windll):
        result = sc.lock_screen()
        mock_windll.user32.LockWorkStation.assert_called_once()
        self.assertEqual(result, "Screen locked.")


class Registration(unittest.TestCase):
    def test_registers_three_tools_with_correct_confirmation_flags(self):
        reg = FakeRegistry()
        sc.register_system_control(reg)
        self.assertEqual(set(reg.registered), {"open_application", "close_application", "lock_screen"})
        self.assertFalse(reg.registered["open_application"]["requires_confirmation"])
        self.assertTrue(reg.registered["close_application"]["requires_confirmation"])
        self.assertFalse(reg.registered["lock_screen"]["requires_confirmation"])


if __name__ == "__main__":
    unittest.main()
