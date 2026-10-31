"""
Apple Calendar.

Two ways in, tried in this order:

1. iCloud CalDAV -- sees every calendar on the account, including private
   ones, and picks up edits within a refresh cycle. Needs an app-specific
   password from appleid.apple.com.
2. A published .ics URL -- zero credentials, but only covers calendars you
   have explicitly shared, and Apple's published feeds lag by a few minutes.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import requests

import config


def _as_local(value) -> datetime:
    """Normalise a date or naive/aware datetime into local-aware datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=config.TIMEZONE)
        return value.astimezone(config.TIMEZONE)
    # A bare date means an all-day event.
    return datetime.combine(value, time.min, tzinfo=config.TIMEZONE)


def _format(events: list[dict]) -> list[dict]:
    """Sort, trim, and add the human-facing day/time strings."""
    today = datetime.now(config.TIMEZONE).date()
    tomorrow = today + timedelta(days=1)

    events.sort(key=lambda e: (e["start"], e["title"]))
    out = []
    for ev in events[: config.CALENDAR_MAX_EVENTS]:
        start = ev["start"]
        day = start.date()
        if day == today:
            day_label = "Today"
        elif day == tomorrow:
            day_label = "Tomorrow"
        else:
            day_label = start.strftime("%a")

        out.append({
            "title": ev["title"],
            "day": day_label,
            "is_today": day == today,
            "time": "all day" if ev["all_day"] else start.strftime("%-I:%M"),
            "location": ev.get("location", ""),
        })
    return out


# ------------------------------------------------------------------ caldav --
def _from_caldav(start: datetime, end: datetime) -> list[dict]:
    import caldav

    client = caldav.DAVClient(
        url=config.ICLOUD_URL,
        username=config.ICLOUD_USERNAME,
        password=config.ICLOUD_PASSWORD,
    )
    principal = client.principal()

    events = []
    for cal in principal.calendars():
        name = str(cal.name or "")
        if config.CALENDAR_NAMES and name not in config.CALENDAR_NAMES:
            continue

        # expand=True makes the server unroll recurring events for us.
        try:
            results = cal.search(start=start, end=end, event=True, expand=True)
        except Exception:
            continue

        for item in results:
            for component in item.icalendar_instance.walk("VEVENT"):
                dtstart = component.get("DTSTART")
                if dtstart is None:
                    continue
                raw = dtstart.dt
                events.append({
                    "title": str(component.get("SUMMARY", "Busy")),
                    "location": str(component.get("LOCATION", "")),
                    "start": _as_local(raw),
                    "all_day": not isinstance(raw, datetime),
                })
    return events


# --------------------------------------------------------------------- ics --
def _from_ics(start: datetime, end: datetime) -> list[dict]:
    import icalendar
    import recurring_ical_events

    url = config.ICS_URL.replace("webcal://", "https://")
    resp = requests.get(url, timeout=20, headers={"User-Agent": config.USER_AGENT})
    resp.raise_for_status()

    cal = icalendar.Calendar.from_ical(resp.text)
    occurrences = recurring_ical_events.of(cal).between(start, end)

    events = []
    for component in occurrences:
        raw = component.get("DTSTART").dt
        events.append({
            "title": str(component.get("SUMMARY", "Busy")),
            "location": str(component.get("LOCATION", "")),
            "start": _as_local(raw),
            "all_day": not isinstance(raw, datetime),
        })
    return events


def fetch() -> dict:
    now = datetime.now(config.TIMEZONE)
    # Start at midnight so today's earlier events still show until the day ends.
    start = datetime.combine(now.date(), time.min, tzinfo=config.TIMEZONE)
    end = start + timedelta(days=config.CALENDAR_DAYS_AHEAD)

    if config.ICLOUD_USERNAME and config.ICLOUD_PASSWORD:
        events = _from_caldav(start, end)
        source = "icloud"
    elif config.ICS_URL:
        events = _from_ics(start, end)
        source = "ics"
    else:
        return {"events": [], "source": "unconfigured"}

    # Hide events that already ended today; keep anything still upcoming.
    cutoff = now - timedelta(minutes=30)
    events = [e for e in events if e["all_day"] or e["start"] >= cutoff]

    return {"events": _format(events), "source": source}


if __name__ == "__main__":
    for ev in fetch()["events"]:
        print(f"{ev['day']:<9} {ev['time']:<8} {ev['title']}")
