"""
"On this day", from Wikipedia's curated feed.

Cheap to be polite about: the answer only changes at midnight, so this caches
by date and makes one request a day regardless of how often the poller runs.
The screen cycles through the list on its own clock -- see `rotate()` in
dashboard/app.py.
"""
from __future__ import annotations

import re
from datetime import date, datetime

import requests

import config

ENDPOINT = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected/{mm}/{dd}"

# Facts that mention these get a small marker -- it is a New York apartment.
LOCAL_HINTS = re.compile(
    r"\b(new york|brooklyn|manhattan|queens|bronx|staten island|coney island)\b",
    re.IGNORECASE,
)

_cache: dict[str, dict] = {}


def _tidy(text: str) -> str:
    text = " ".join(text.split())
    # Wikipedia sometimes leaves a trailing parenthetical citation artefact.
    return text.rstrip(" .;,") + "."


def fetch() -> dict:
    today = datetime.now(config.TIMEZONE).date()
    key = today.isoformat()
    if key in _cache:
        return _cache[key]

    resp = requests.get(
        ENDPOINT.format(mm=f"{today.month:02d}", dd=f"{today.day:02d}"),
        headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()

    items = []
    for entry in resp.json().get("selected", []):
        text = _tidy(entry.get("text", ""))
        year = entry.get("year")
        if not text or year is None or len(text) > config.FACT_MAX_CHARS:
            continue
        items.append({
            "year": abs(year),
            "era": "BC" if year < 0 else "",
            "text": text,
            "local": bool(LOCAL_HINTS.search(text)),
        })

    if not items:
        raise RuntimeError("no usable entries in the on-this-day feed")

    result = {
        "date_label": today.strftime("%B %-d"),
        "items": items,
        "credit": "Wikipedia",
    }

    _cache.clear()          # only ever hold today
    _cache[key] = result
    return result


if __name__ == "__main__":
    data = fetch()
    print(data["date_label"])
    for item in data["items"]:
        mark = "*" if item["local"] else " "
        print(f" {mark} {item['year']}{item['era']}  {item['text']}")
