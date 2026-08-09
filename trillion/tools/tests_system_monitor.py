"""Tests for the system monitor tool. Stdlib unittest + mock."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from trillion.tools import system_monitor as sm


class FakeRegistry:
    def __init__(self):
        self.registered = {}

    def register(self, name, description, input_schema, fn, requires_confirmation=False):
        self.registered[name] = {"fn": fn, "requires_confirmation": requires_confirmation}


class SystemStatus(unittest.TestCase):
    @patch("psutil.disk_usage")
    @patch("psutil.boot_time")
    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    def test_reports_all_sections(self, mock_cpu, mock_mem, mock_boot, mock_disk):
        mock_cpu.return_value = 12.3
        mock_mem.return_value = MagicMock(used=4 * 1024**3, total=16 * 1024**3, percent=25.0)
        mock_disk.return_value = MagicMock(used=100 * 1024**3, total=500 * 1024**3, percent=20.0)
        mock_boot.return_value = 0.0
        with patch("time.time", return_value=3661.0):  # 1h 1m 1s uptime
            result = sm.system_status()
        self.assertIn("CPU: 12%", result)
        self.assertIn("Memory:", result)
        self.assertIn("Disk", result)
        self.assertIn("Uptime:", result)


class TakeScreenshot(unittest.TestCase):
    @patch("sys.platform", "linux")
    def test_non_windows_is_rejected(self):
        result = sm.take_screenshot()
        self.assertIn("only supported on Windows", result)

    @patch("PIL.ImageGrab.grab")
    def test_saves_a_png_and_returns_path(self, mock_grab):
        mock_img = MagicMock()
        mock_grab.return_value = mock_img
        result = sm.take_screenshot()
        mock_img.save.assert_called_once()
        saved_path = mock_img.save.call_args[0][0]
        self.assertTrue(str(saved_path).endswith(".png"))
        self.assertIn("Screenshot saved", result)

    @patch("PIL.ImageGrab.grab", side_effect=OSError("no display"))
    def test_grab_error_is_reported_not_raised(self, mock_grab):
        result = sm.take_screenshot()
        self.assertIn("Couldn't capture", result)


class Registration(unittest.TestCase):
    def test_registers_two_tools_with_correct_confirmation_flags(self):
        reg = FakeRegistry()
        sm.register_system_monitor(reg)
        self.assertEqual(set(reg.registered), {"system_status", "take_screenshot"})
        self.assertFalse(reg.registered["system_status"]["requires_confirmation"])
        self.assertTrue(reg.registered["take_screenshot"]["requires_confirmation"])


if __name__ == "__main__":
    unittest.main()
