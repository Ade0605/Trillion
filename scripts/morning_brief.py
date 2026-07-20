"""
Spoken morning brief — calendar + reminders, read aloud through the speakers.

Run by Windows Task Scheduler each morning. Unattended: it does not need a
browser (browsers block autoplay), it plays audio locally via ElevenLabs.

    python scripts/morning_brief.py            # speak it
    python scripts/morning_brief.py --dry-run  # print only, no audio
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


def _greeting(now: _dt.datetime) -> str:
    h = now.hour
    if h < 12:
        return "Good morning"
    if h < 18:
        return "Good afternoon"
    return "Good evening"


def _reminders_part() -> str:
    if not _REMINDERS.exists():
        return ""
    try:
        items = json.loads(_REMINDERS.read_text(encoding="utf-8"))
    except Exception:
        return ""
    pending = [i for i in items if not i.get("done")]
    if not pending:
        return "No reminders pending."
    if len(pending) == 1:
        return f"One reminder: {pending[0].get('text', '').strip()}."
    heads = "; ".join((i.get("text", "") or "").strip() for i in pending[:5])
    tail = f", plus {len(pending) - 5} more" if len(pending) > 5 else ""
    return f"{len(pending)} reminders: {heads}{tail}."


def _calendar_part() -> str:
    try:
        from trillion import calendar_yahoo as cal
    except Exception:
        return ""
    if not cal.configured():
        return ""
    try:
        return cal.summarise(cal.todays_events())
    except cal.CalendarError as e:
        # Speak a short, honest failure rather than pretending the day is empty.
        return f"I could not reach your calendar. {e}"


def _sessions_part(limit: int = 5) -> str:
    """Top N most recent Claude Code sessions, spoken form. Never raises — a
    session-reader failure must not cost the user their calendar."""
    try:
        from trillion.claude_sessions import recent_sessions, summarise
        sessions = recent_sessions(limit)
    except Exception:
        return ""
    if not sessions:
        return ""
    return summarise(sessions, speakable=True)


def build_brief(now: _dt.datetime | None = None) -> str:
    now = now or _dt.datetime.now().astimezone()
    parts = [f"{_greeting(now)}. It's {now.strftime('%A, %B %d')}."]
    cal_part = _calendar_part()
    if cal_part:
        parts.append(cal_part)
    rem = _reminders_part()
    if rem:
        parts.append(rem)
    sess = _sessions_part()
    if sess:
        parts.append(sess)
    return " ".join(p for p in parts if p)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(prog="morning_brief")
    ap.add_argument("--dry-run", action="store_true", help="print the brief, do not speak")
    args = ap.parse_args()

    text = build_brief()
    print(text)

    if args.dry_run:
        return 0

    try:
        from trillion.voice.tts import speak
        speak(text)
    except Exception as e:
        print(f"[speak failed: {type(e).__name__}] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
