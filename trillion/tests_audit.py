"""Tests for the audit log's tool-run history reader. Stdlib unittest."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from trillion import audit


class RecentToolRuns(unittest.TestCase):
    def test_missing_log_returns_empty(self):
        with patch.object(audit, "_LOG") as mock_log:
            mock_log.exists.return_value = False
            self.assertEqual(audit.recent_tool_runs(), [])

    def test_filters_to_tool_run_events_newest_first(self):
        lines = [
            json.dumps({"event": "tool_run", "tool": "add_reminder", "ts": "1"}),
            json.dumps({"event": "confirmation", "tool": "delete_reminder", "ts": "2"}),
            json.dumps({"event": "tool_run", "tool": "list_reminders", "ts": "3"}),
        ]
        with patch.object(audit, "_LOG") as mock_log:
            mock_log.exists.return_value = True
            mock_log.read_text.return_value = "\n".join(lines)
            result = audit.recent_tool_runs()
        self.assertEqual([e["tool"] for e in result], ["list_reminders", "add_reminder"])

    def test_corrupt_line_is_skipped_not_raised(self):
        lines = ["not json", json.dumps({"event": "tool_run", "tool": "ok", "ts": "1"})]
        with patch.object(audit, "_LOG") as mock_log:
            mock_log.exists.return_value = True
            mock_log.read_text.return_value = "\n".join(lines)
            result = audit.recent_tool_runs()
        self.assertEqual(len(result), 1)

    def test_respects_limit(self):
        lines = [json.dumps({"event": "tool_run", "tool": f"t{i}", "ts": str(i)}) for i in range(5)]
        with patch.object(audit, "_LOG") as mock_log:
            mock_log.exists.return_value = True
            mock_log.read_text.return_value = "\n".join(lines)
            result = audit.recent_tool_runs(limit=2)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
