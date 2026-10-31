"""
The web layer.

Deliberately thin. All rendering happens server-side in Jinja; the browser
runs four lines of JavaScript whose only job is to swap in a freshly rendered
fragment. That keeps every formatting decision in Python where you can test it.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from flask import Flask, render_template

import config
from dashboard import poller

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("dashboard.app")

app = Flask(__name__)


def setting(name: str, default):
    """
    Read a config value that may be missing from an older config.py.

    Settings get added over time, and a stale config file must not be able to
    crash the render -- a board showing slightly wrong numbers beats a board
    showing a 500 page.
    """
    return getattr(config, name, default)


def news_count(section: str) -> int:
    """NEWS_SHOWN is per-section now, but older configs hold a plain int."""
    value = setting("NEWS_SHOWN", {"nyc": 2, "national": 1})
    if isinstance(value, dict):
        return int(value.get(section, 2))
    return int(value)


def rotate(items: list, size: int, seconds: int) -> list:
    """
    Pick the slice to show right now, derived purely from wall time.

    No cursor, no session, no client state: every render computes the same
    answer from the clock, so the panel advances on schedule and two browsers
    pointed at the board stay in step. The window wraps, so a pool that does
    not divide evenly still cycles through everything.
    """
    if not items:
        return []
    if len(items) <= size:
        return items
    offset = (int(time.time() // seconds) * size) % len(items)
    return [items[(offset + i) % len(items)] for i in range(size)]


def _pick_fact(otd: dict | None) -> dict | None:
    """One fact, changing on its own slow clock."""
    if not otd or not otd.get("items"):
        return None
    items = otd["items"]
    index = int(time.time() // setting("FACT_ROTATE_SECONDS", 420)) % len(items)
    return items[index]


def _context() -> dict:
    now = datetime.now(config.TIMEZONE)
    snap = poller.snapshot()
    news = poller.get("news")
    otd = poller.get("onthisday")

    return {
        "clock": now.strftime("%-I:%M"),
        "meridiem": now.strftime("%p").lower(),
        "date": now.strftime("%A, %B %-d"),
        "subway": poller.get("subway"),
        "subway_stale": poller.stale("subway"),
        "weather": poller.get("weather"),
        "calendar": poller.get("calendar"),
        "citibike": poller.get("citibike"),
        "air": poller.get("airquality"),
        "nyc_news": rotate(news["nyc"], news_count("nyc"),
                           setting("NEWS_ROTATE_SECONDS", 45)) if news else [],
        "national_news": rotate(news["national"], news_count("national"),
                                setting("NEWS_ROTATE_SECONDS", 45)) if news else [],
        "has_news": bool(news),
        "otd": otd,
        "fact": _pick_fact(otd),
        "problems": [k for k, v in snap.items() if not v.get("ok")],
    }


@app.route("/")
def index():
    return render_template("index.html", **_context())


@app.route("/panel")
def panel():
    """The live region, re-rendered and swapped in by the page every 15s."""
    return render_template("panel.html", **_context())


@app.errorhandler(Exception)
def on_error(exc):
    """
    Never show the stock 500 page on a wall panel. Log the traceback, then
    return something legible on the board's own background so the screen
    stays readable and the next 15-second refresh can recover on its own.
    """
    log.exception("render failed")
    return (
        "<div style=\"background:#08090B;color:#FFB000;font:600 2vh "
        "Helvetica,Arial,sans-serif;padding:2vh\">Dashboard error &mdash; "
        "run: journalctl --user -u dashboard -n 40</div>",
        200,
    )


@app.route("/healthz")
def healthz():
    snap = poller.snapshot()
    try:
        render_template("panel.html", **_context())
        renders = True
        render_error = None
    except Exception as exc:                       # noqa: BLE001
        renders = False
        render_error = str(exc)

    return {
        "renders": renders,
        "render_error": render_error,
        "sources": {k: {"ok": v.get("ok"), "error": v.get("error")}
                    for k, v in snap.items()},
    }


def main() -> None:
    poller.start()
    app.run(host=config.HOST, port=config.PORT, threaded=True)


if __name__ == "__main__":
    main()
