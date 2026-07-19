"""
Probe the Yahoo CalDAV connection. Prints diagnostics only — never the password.

    python scripts/probe_yahoo_calendar.py
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from trillion import calendar_yahoo as cal  # noqa: E402


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if not cal.configured():
        print("NOT CONFIGURED — add to .env:")
        print("  YAHOO_CALDAV_USER=you@yahoo.com")
        print("  YAHOO_CALDAV_APP_PASSWORD=<Yahoo app password>")
        print("\nGenerate at: Yahoo Account Security -> Generate app password.")
        return 2

    print("credentials: present")
    try:
        principal = cal._principal()
        print("auth: OK")
    except cal.CalendarError as e:
        print(f"auth: FAILED — {e}")
        return 1

    try:
        cals = principal.calendars()
        print(f"calendars found: {len(cals)}")
        for c in cals:
            try:
                print(f"  - {c.name or '(unnamed)'}")
            except Exception:
                print("  - (unreadable name)")
    except Exception as e:
        print(f"calendar list: FAILED — {type(e).__name__}")
        return 1

    tz = _dt.datetime.now().astimezone().tzinfo
    now = _dt.datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        week = cal.events_between(start, start + _dt.timedelta(days=7))
        print(f"\nevents next 7 days: {len(week)}")
        for e in week[:15]:
            print(f"  {e.start} | {e.summary}")
    except cal.CalendarError as e:
        print(f"event read: FAILED — {e}")
        return 1

    print("\nPROBE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
