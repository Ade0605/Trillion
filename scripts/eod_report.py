"""
Spoken end-of-day report on Claude Code activity.

Run by the "Trillion EOD Report" scheduled task at 17:30 and 18:30. Like the
morning brief this runs as a *user* task, not the service: services live in
Session 0 and cannot play audio to the desktop.

    python scripts/eod_report.py            # speak it
    python scripts/eod_report.py --dry-run  # print only
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

_REMINDERS = ROOT / "data" / "reminders.json"
# Two triggers fire an hour apart; don't repeat the same report twice.
_STAMP = ROOT / "data" / ".eod_last.json"


def _open_reminders() -> str:
    if not _REMINDERS.exists():
        return ""
    try:
        items = json.loads(_REMINDERS.read_text(encoding="utf-8"))
    except Exception:
        return ""
    pending = [i for i in items if not i.get("done")]
    if not pending:
        return "Nothing left on your reminders."
    if len(pending) == 1:
        return f"One reminder still open: {(pending[0].get('text') or '').strip()}."
    heads = "; ".join((i.get("text") or "").strip() for i in pending[:3])
    tail = f", plus {len(pending) - 3} more" if len(pending) > 3 else ""
    return f"{len(pending)} reminders still open: {heads}{tail}."


def _sessions_part() -> str:
    try:
        from trillion.claude_sessions import sessions_today, day_report
        return day_report(sessions_today(), speakable=True)
    except Exception:
        return "I couldn't read your Claude Code sessions."


def _open_face() -> None:
    """Put the cosmic /face UI on screen instead of a bare terminal."""
    import os
    import webbrowser
    port = os.environ.get("TRILLION_PORT", "7777")
    try:
        webbrowser.open(f"http://localhost:{port}/face")
    except Exception:
        pass


def build_report(now: _dt.datetime | None = None) -> str:
    now = now or _dt.datetime.now().astimezone()
    parts = [_sessions_part()]
    rem = _open_reminders()
    if rem:
        parts.append(rem)
    return " ".join(p for p in parts if p)


def _already_reported_recently(window_minutes: int = 45) -> bool:
    """True when a report ran inside the window — the 17:30 and 18:30 triggers
    are an hour apart, so this only suppresses accidental double-fires (a
    missed task catching up, or a manual run right before a trigger)."""
    try:
        data = json.loads(_STAMP.read_text(encoding="utf-8"))
        last = _dt.datetime.fromisoformat(data["at"])
    except Exception:
        return False
    return (_dt.datetime.now().astimezone() - last).total_seconds() < window_minutes * 60


def _stamp() -> None:
    try:
        _STAMP.parent.mkdir(parents=True, exist_ok=True)
        _STAMP.write_text(json.dumps({"at": _dt.datetime.now().astimezone().isoformat()}),
                          encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(prog="eod_report")
    ap.add_argument("--dry-run", action="store_true", help="print, do not speak")
    ap.add_argument("--force", action="store_true", help="speak even if one just ran")
    args = ap.parse_args()

    text = build_report()
    print(text)

    if args.dry_run:
        return 0
    if not args.force and _already_reported_recently():
        print("[skipped: a report already ran in the last 45 minutes]")
        return 0

    _open_face()

    try:
        from trillion.voice.tts import speak
        speak(text)
        _stamp()
    except Exception as e:
        print(f"[speak failed: {type(e).__name__}] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
