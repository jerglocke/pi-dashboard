"""
Background refresh.

Each source runs on its own thread and its own interval, writing into a shared
snapshot. The web request never blocks on the network -- it reads whatever is
in the snapshot and returns immediately. A source that fails keeps its last
good value and records the error, so one dead API dims one panel instead of
taking down the whole board.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

import config
from dashboard.sources import (
    calendar_source, extras, news, onthisday, subway, weather,
)

log = logging.getLogger("dashboard.poller")

_lock = threading.Lock()
_state: dict[str, dict] = {}

SOURCES = {
    "subway": subway.fetch,
    "weather": weather.fetch,
    "calendar": calendar_source.fetch,
    "citibike": extras.fetch_citibike,
    "airquality": extras.fetch_air_quality,
    "news": news.fetch,
    "onthisday": onthisday.fetch,
}


def _run(name: str, fn) -> None:
    interval = config.REFRESH_SECONDS.get(name, 300)
    backoff = 0

    while True:
        try:
            data = fn()
            with _lock:
                _state[name] = {
                    "data": data,
                    "ok": True,
                    "error": None,
                    "fetched_at": datetime.now(config.TIMEZONE),
                }
            backoff = 0
        except Exception as exc:                      # noqa: BLE001
            log.warning("%s refresh failed: %s", name, exc)
            with _lock:
                prev = _state.get(name, {})
                _state[name] = {
                    "data": prev.get("data"),         # keep last good value
                    "ok": False,
                    "error": str(exc),
                    "fetched_at": prev.get("fetched_at"),
                }
            # Ease off a struggling endpoint, up to 5 minutes.
            backoff = min(300, (backoff or interval) * 2)

        time.sleep(backoff or interval)


def start() -> None:
    """Kick off one daemon thread per source."""
    for name, fn in SOURCES.items():
        if name == "citibike" and config.CITIBIKE_STATION_COUNT <= 0:
            continue
        if name == "airquality" and not config.SHOW_AIR_QUALITY:
            continue
        threading.Thread(target=_run, args=(name, fn), daemon=True,
                         name=f"poll-{name}").start()


def snapshot() -> dict:
    """A consistent, copy-on-read view of every source."""
    with _lock:
        return {k: dict(v) for k, v in _state.items()}


def get(name: str) -> dict | None:
    with _lock:
        entry = _state.get(name)
        return entry.get("data") if entry else None


def stale(name: str, tolerance: float = 3.0) -> bool:
    """True if a source has not produced fresh data in `tolerance` intervals."""
    with _lock:
        entry = _state.get(name)
    if not entry or not entry.get("fetched_at"):
        return True
    age = (datetime.now(config.TIMEZONE) - entry["fetched_at"]).total_seconds()
    return age > config.REFRESH_SECONDS.get(name, 300) * tolerance
