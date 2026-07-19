"""
Yahoo Calendar over CalDAV — read-only.

Credentials live in .env and are never logged:
    YAHOO_CALDAV_USER          your Yahoo address, e.g. you@yahoo.com
    YAHOO_CALDAV_APP_PASSWORD  a Yahoo *app password*, NOT the account password
    YAHOO_CALDAV_URL           optional override of the CalDAV endpoint

Yahoo requires an app password (Account Security -> Generate app password);
the normal password is rejected since less-secure-app logins were disabled.

Recurring events are expanded with recurring_ical_events, so a weekly standup
shows up on each day it actually occurs rather than only on its start date.
All times are normalised to the local timezone for display.
"""
from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass

DEFAULT_URL = "https://caldav.calendar.yahoo.com"

# Cache the last successful read so a Yahoo outage degrades to stale data
# instead of an empty brief.
_cache: dict = {"events": None, "at": None, "day": None}


class CalendarError(RuntimeError):
    """Calendar unreachable or misconfigured. Message is safe to show; it never
    contains the password."""


@dataclass
class Event:
    summary: str
    start: _dt.datetime | _dt.date
    end: _dt.datetime | _dt.date | None
    location: str = ""
    all_day: bool = False

    def when(self) -> str:
        """Short human/speakable time, e.g. '9:30 AM' or 'all day'."""
        if self.all_day:
            return "all day"
        try:
            return self.start.strftime("%-I:%M %p")
        except ValueError:          # Windows has no %-I
            return self.start.strftime("%I:%M %p").lstrip("0")

    def line(self) -> str:
        bits = f"{self.when()} — {self.summary}"
        if self.location:
            bits += f" ({self.location})"
        return bits


def configured() -> bool:
    return bool(os.environ.get("YAHOO_CALDAV_USER", "").strip()
                and os.environ.get("YAHOO_CALDAV_APP_PASSWORD", "").strip())


def _principal():
    import caldav

    user = os.environ.get("YAHOO_CALDAV_USER", "").strip()
    pw = os.environ.get("YAHOO_CALDAV_APP_PASSWORD", "").strip()
    url = os.environ.get("YAHOO_CALDAV_URL", "").strip() or DEFAULT_URL
    if not user or not pw:
        raise CalendarError(
            "Yahoo calendar not configured — set YAHOO_CALDAV_USER and "
            "YAHOO_CALDAV_APP_PASSWORD in .env (use a Yahoo app password)."
        )
    try:
        client = caldav.DAVClient(url=url, username=user, password=pw)
        return client.principal()
    except Exception as e:
        # Never echo the password; surface only the failure class.
        raise CalendarError(f"Could not reach Yahoo CalDAV ({type(e).__name__}). "
                            f"Check the app password and that CalDAV is enabled.") from None


def _local_tz() -> _dt.tzinfo:
    return _dt.datetime.now().astimezone().tzinfo


def _to_local(value):
    """Normalise an ical date/datetime to local tz; keep pure dates as dates."""
    if isinstance(value, _dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=_local_tz())
        return value.astimezone(_local_tz())
    return value


def events_between(start: _dt.datetime, end: _dt.datetime) -> list[Event]:
    """All events overlapping [start, end), recurrences expanded."""
    import recurring_ical_events
    from icalendar import Calendar as ICalendar

    principal = _principal()
    out: list[Event] = []
    try:
        calendars = principal.calendars()
    except Exception as e:
        raise CalendarError(f"Could not list calendars ({type(e).__name__}).") from None

    for cal in calendars:
        try:
            raw = cal.get_supported_components()
            if raw and "VEVENT" not in raw:
                continue
        except Exception:
            pass
        try:
            # Pull the raw icalendar data so recurrence expansion is ours, not
            # the server's — Yahoo's expansion support is inconsistent.
            for obj in cal.events():
                try:
                    ical = ICalendar.from_ical(obj.data)
                except Exception:
                    continue
                for comp in recurring_ical_events.of(ical).between(start, end):
                    summary = str(comp.get("SUMMARY", "") or "").strip() or "(untitled)"
                    dtstart = comp.get("DTSTART")
                    dtend = comp.get("DTEND")
                    sv = dtstart.dt if dtstart is not None else None
                    ev = dtend.dt if dtend is not None else None
                    if sv is None:
                        continue
                    all_day = not isinstance(sv, _dt.datetime)
                    out.append(Event(
                        summary=summary,
                        start=_to_local(sv),
                        end=_to_local(ev) if ev is not None else None,
                        location=str(comp.get("LOCATION", "") or "").strip(),
                        all_day=all_day,
                    ))
        except Exception:
            # One bad calendar must not sink the whole brief.
            continue

    def _key(e: Event):
        s = e.start
        if isinstance(s, _dt.datetime):
            return (0, s.timestamp())
        return (-1, 0)      # all-day first

    out.sort(key=_key)
    return out


def todays_events(use_cache_on_error: bool = True) -> list[Event]:
    """Events for the rest of today (all-day events always included)."""
    tz = _local_tz()
    now = _dt.datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + _dt.timedelta(days=1)
    today = start.date()
    try:
        evs = events_between(start, end)
        _cache.update({"events": evs, "at": now, "day": today})
        return evs
    except CalendarError:
        if use_cache_on_error and _cache["events"] is not None and _cache["day"] == today:
            return _cache["events"]
        raise


def summarise(events: list[Event], max_items: int = 8) -> str:
    """Speakable one-paragraph summary of a day's events."""
    if not events:
        return "Nothing on your calendar today."
    shown = events[:max_items]
    lines = [e.line() for e in shown]
    extra = len(events) - len(shown)
    head = f"You have {len(events)} thing{'s' if len(events) != 1 else ''} on today. "
    body = ". ".join(lines)
    tail = f". Plus {extra} more." if extra > 0 else "."
    return head + body + tail
