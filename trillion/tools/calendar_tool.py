"""
Calendar tool — read-only view of the Yahoo calendar.

Read-only by design: Trillion can tell you what's on, but cannot create, move,
or delete events. Writing to a calendar is a gated action and isn't built.
"""
from __future__ import annotations

import datetime as _dt

_SCHEMA = {
    "type": "object",
    "properties": {
        "days": {
            "type": "integer",
            "description": "How many days ahead to look. 0 or 1 = today only. Default 1.",
        }
    },
}

_DESC = (
    "Look at the user's calendar. Returns events for today, or the next N days. "
    "Read-only — cannot add, change, or delete events."
)


def list_calendar_events(days: int = 1) -> str:
    from trillion import calendar_yahoo as cal

    if not cal.configured():
        return ("Calendar isn't connected. Set YAHOO_CALDAV_USER and "
                "YAHOO_CALDAV_APP_PASSWORD in .env (a Yahoo app password).")

    try:
        days = int(days or 1)
    except (TypeError, ValueError):
        days = 1
    days = max(1, min(days, 30))

    tz = _dt.datetime.now().astimezone().tzinfo
    start = _dt.datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        if days <= 1:
            events = cal.todays_events()
            if not events:
                return "Nothing on the calendar today."
            return "Today:\n" + "\n".join("  - " + e.line() for e in events)
        events = cal.events_between(start, start + _dt.timedelta(days=days))
    except cal.CalendarError as e:
        return str(e)

    if not events:
        return f"Nothing on the calendar for the next {days} days."

    by_day: dict = {}
    for e in events:
        key = e.start.date() if isinstance(e.start, _dt.datetime) else e.start
        by_day.setdefault(key, []).append(e)

    out = []
    for day in sorted(by_day):
        out.append(day.strftime("%A %b %d") + ":")
        out += ["  - " + e.line() for e in by_day[day]]
    return "\n".join(out)


def register(registry) -> None:
    registry.register("list_calendar_events", _DESC, _SCHEMA, list_calendar_events,
                      requires_confirmation=False)
