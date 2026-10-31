"""
Live subway departures from the MTA's GTFS-Realtime feed.

No API key required -- the MTA dropped that requirement, the feeds are just
public protobuf over HTTPS now.
"""
from __future__ import annotations

import csv
import io
import time
import zipfile
from datetime import datetime

import requests
from google.transit import gtfs_realtime_pb2

import config

# Official MTA route colours, used for the line bullets on screen.
ROUTE_COLORS = {
    "1": "#EE352E", "2": "#EE352E", "3": "#EE352E",
    "4": "#00933C", "5": "#00933C", "6": "#00933C",
    "7": "#B933AD",
    "A": "#0039A6", "C": "#0039A6", "E": "#0039A6",
    "B": "#FF6319", "D": "#FF6319", "F": "#FF6319", "M": "#FF6319",
    "G": "#6CBE45",
    "J": "#996633", "Z": "#996633",
    "L": "#A7A9AC",
    "N": "#FCCC0A", "Q": "#FCCC0A", "R": "#FCCC0A", "W": "#FCCC0A",
    "S": "#808183", "SIR": "#0039A6",
}

# Routes with a yellow/grey bullet need dark text on top to stay legible.
DARK_TEXT_ROUTES = {"N", "Q", "R", "W", "L", "S"}

STATIC_GTFS = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"


def _fetch_feed(url: str) -> gtfs_realtime_pb2.FeedMessage:
    resp = requests.get(
        url, timeout=12, headers={"User-Agent": config.USER_AGENT}
    )
    resp.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)
    return feed


def _arrivals_for_platform(feed, platform: str, now: float) -> list[dict]:
    """Pull every future arrival at one platform out of the feed."""
    out = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        trip = entity.trip_update.trip
        route = trip.route_id or "?"

        for stu in entity.trip_update.stop_time_update:
            if stu.stop_id != platform:
                continue

            # Some updates carry only one of the two. Prefer departure.
            stamp = 0
            if stu.HasField("departure") and stu.departure.time:
                stamp = stu.departure.time
            elif stu.HasField("arrival") and stu.arrival.time:
                stamp = stu.arrival.time
            if not stamp:
                continue

            minutes = (stamp - now) / 60.0
            # Drop trains already gone, and anything absurdly far out.
            if minutes < -0.5 or minutes > 60:
                continue

            out.append({
                "route": route,
                "color": ROUTE_COLORS.get(route, "#8A9099"),
                "dark_text": route in DARK_TEXT_ROUTES,
                # Round rather than truncate: a train 2.9 minutes out is a
                # 3-minute train, not a 2-minute one.
                "minutes": max(0, round(minutes)),
                "timestamp": stamp,
                "catchable": minutes >= config.WALK_MINUTES,
            })

    out.sort(key=lambda a: a["timestamp"])
    return out


def fetch() -> dict:
    """Return departures grouped by direction, newest data wins."""
    now = time.time()
    feed = _fetch_feed(config.SUBWAY_FEED)

    directions = []
    for spec in config.SUBWAY_DIRECTIONS:
        arrivals = _arrivals_for_platform(feed, spec["platform"], now)
        directions.append({
            "label": spec["label"],
            "trains": arrivals[: config.SUBWAY_COUNT],
        })

    return {
        "station": "Sterling St",
        "walk_minutes": config.WALK_MINUTES,
        "directions": directions,
        "feed_age": int(now - feed.header.timestamp) if feed.header.timestamp else None,
        "updated": datetime.now(config.TIMEZONE).strftime("%-I:%M"),
    }


# ------------------------------------------------------------------ lookup --
def find_stop(query: str) -> list[tuple[str, str]]:
    """
    One-off helper: download the static GTFS bundle and grep stops.txt so you
    can find the stop_id for any station. Run it like:

        python -m dashboard.sources.subway --find "Winthrop"
    """
    resp = requests.get(STATIC_GTFS, timeout=90,
                        headers={"User-Agent": config.USER_AGENT})
    resp.raise_for_status()

    matches = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("stops.txt") as fh:
            reader = csv.DictReader(io.TextIOWrapper(fh, "utf-8-sig"))
            for row in reader:
                if query.lower() in row["stop_name"].lower():
                    matches.append((row["stop_id"], row["stop_name"]))
    return matches


if __name__ == "__main__":
    import sys

    if "--find" in sys.argv:
        term = sys.argv[sys.argv.index("--find") + 1]
        for stop_id, name in find_stop(term):
            print(f"{stop_id:<8} {name}")
    else:
        data = fetch()
        for d in data["directions"]:
            print(f"\n{d['label']}")
            for t in d["trains"]:
                mark = " " if t["catchable"] else "x"
                print(f"  {mark} {t['route']}  {t['minutes']} min")
