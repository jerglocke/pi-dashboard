"""
News headlines from RSS.

Headlines only -- no article text, no summaries. That is partly a copyright
question and partly a design one: a wall panel you read from eight feet away
has room for a headline and nothing else.

Feeds rot. Run the checker before you trust a change:

    python -m dashboard.sources.news --check
"""
from __future__ import annotations

import calendar as _calendar
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor

import feedparser
import requests

import config

_TAGS = re.compile(r"<[^>]+>")
_NOISE = re.compile(r"[^a-z0-9 ]+")


def _clean(title: str) -> str:
    """Feeds are inconsistent about entities and stray markup."""
    return " ".join(_TAGS.sub("", html.unescape(title)).split())


def _key(title: str) -> str:
    """Normalised form, so two outlets running the same story collapse."""
    return _NOISE.sub("", title.lower())[:60]


def _age(epoch: float | None, now: float) -> str:
    if not epoch:
        return ""
    mins = (now - epoch) / 60
    if mins < 1:
        return "now"
    if mins < 60:
        return f"{round(mins)}m"
    if mins < 60 * 24:
        return f"{round(mins / 60)}h"
    return f"{round(mins / 1440)}d"


def _published(entry) -> float | None:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            return _calendar.timegm(parsed)
    return None


def _pull(feed: dict) -> list[dict]:
    """Fetch and parse one feed. Raises on failure; the caller decides."""
    resp = requests.get(
        feed["url"],
        timeout=12,
        headers={"User-Agent": config.USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml"},
    )
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)

    items = []
    for entry in parsed.entries[: config.NEWS_PER_FEED]:
        title = _clean(entry.get("title", ""))
        if len(title) < 12:          # nav links, section stubs, empty items
            continue
        items.append({
            "title": title,
            "source": feed["name"],
            "section": feed["section"],
            "epoch": _published(entry),
        })
    return items


def fetch() -> dict:
    now = time.time()
    collected: list[dict] = []
    failures: list[str] = []

    # Feeds are slow and independent, so fetch them side by side. The whole
    # panel then costs about as long as the slowest single feed.
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_pull, f): f for f in config.NEWS_FEEDS}
        for future, feed in futures.items():
            try:
                collected.extend(future.result())
            except Exception:                        # noqa: BLE001
                failures.append(feed["name"])

    if not collected:
        raise RuntimeError(f"every news feed failed: {', '.join(failures)}")

    sections: dict[str, list[dict]] = {"nyc": [], "national": []}
    seen: set[str] = set()

    def place(name: str) -> None:
        bucket = sections[name]
        for item in ordered:
            if item["section"] != name or len(bucket) >= config.NEWS_POOL:
                continue
            key = _key(item["title"])
            if key in seen:
                continue
            seen.add(key)
            bucket.append({
                "title": item["title"],
                "source": item["source"],
                "age": _age(item["epoch"], now),
            })

    # Freshest first, and the first outlet to file a story keeps it.
    ordered = sorted(collected, key=lambda i: i["epoch"] or 0, reverse=True)

    # Local fills first on purpose. When a city story also moves on a national
    # wire, it belongs under New York, not under National.
    place("nyc")
    place("national")

    return {
        "nyc": sections["nyc"],
        "national": sections["national"],
        "failed": failures,
    }


def check() -> None:
    """Report which configured feeds actually work right now."""
    for feed in config.NEWS_FEEDS:
        try:
            items = _pull(feed)
            sample = items[0]["title"][:58] if items else "(no entries)"
            print(f"  ok    {feed['name']:<18} {len(items):>2} items   {sample}")
        except Exception as exc:                     # noqa: BLE001
            print(f"  FAIL  {feed['name']:<18} {exc}")


if __name__ == "__main__":
    import sys

    if "--check" in sys.argv:
        check()
    else:
        data = fetch()
        for section in ("nyc", "national"):
            print(f"\n{section}")
            for item in data[section]:
                print(f"  [{item['age']:>3}] {item['source']}: {item['title']}")
