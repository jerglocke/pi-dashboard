"""
The small stuff: nearest Citi Bike docks, and air quality.

Both are keyless. Citi Bike publishes GBFS, the open standard every bikeshare
system uses, so this module works unchanged in any GBFS city -- just swap the
feed URL.
"""
from __future__ import annotations

import math

import requests

import config

GBFS_INFO = "https://gbfs.citibikenyc.com/gbfs/en/station_information.json"
GBFS_STATUS = "https://gbfs.citibikenyc.com/gbfs/en/station_status.json"
AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"

_station_cache: list[dict] = []


def _distance_m(lat1, lon1, lat2, lon2) -> float:
    """Haversine. Good enough at neighbourhood scale."""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _nearest_stations() -> list[dict]:
    """Station locations barely change, so resolve them once per process."""
    global _station_cache
    if _station_cache:
        return _station_cache

    resp = requests.get(GBFS_INFO, timeout=15)
    resp.raise_for_status()
    stations = resp.json()["data"]["stations"]

    for s in stations:
        s["_distance"] = _distance_m(
            config.LATITUDE, config.LONGITUDE, s["lat"], s["lon"]
        )
    stations.sort(key=lambda s: s["_distance"])
    _station_cache = stations[: config.CITIBIKE_STATION_COUNT]
    return _station_cache


def fetch_citibike() -> dict:
    nearby = _nearest_stations()
    wanted = {s["station_id"] for s in nearby}

    resp = requests.get(GBFS_STATUS, timeout=15)
    resp.raise_for_status()
    status = {
        s["station_id"]: s
        for s in resp.json()["data"]["stations"]
        if s["station_id"] in wanted
    }

    out = []
    for s in nearby:
        live = status.get(s["station_id"], {})
        types = live.get("num_bikes_available_types", {})
        out.append({
            "name": s["name"],
            "walk": max(1, round(s["_distance"] / 80)),   # ~80 m/min
            "bikes": live.get("num_bikes_available", 0),
            "ebikes": types.get("ebike", 0),
            "docks": live.get("num_docks_available", 0),
        })
    return {"stations": out}


# Standard US AQI breakpoints, so the colour means what people expect.
AQI_BANDS = [
    (50, "Good", "#00E400"),
    (100, "Moderate", "#FFB000"),
    (150, "Unhealthy if sensitive", "#FF7E00"),
    (200, "Unhealthy", "#EE352E"),
    (300, "Very unhealthy", "#8F3F97"),
    (10_000, "Hazardous", "#7E0023"),
]


def fetch_air_quality() -> dict:
    resp = requests.get(
        AIR_QUALITY,
        params={
            "latitude": config.LATITUDE,
            "longitude": config.LONGITUDE,
            "current": "us_aqi,pm2_5",
            "timezone": "America/New_York",
        },
        timeout=12,
    )
    resp.raise_for_status()
    cur = resp.json()["current"]
    aqi = cur.get("us_aqi")
    if aqi is None:
        return {}

    label, color = next((l, c) for limit, l, c in AQI_BANDS if aqi <= limit)
    return {"aqi": round(aqi), "label": label, "color": color}


if __name__ == "__main__":
    import json
    print(json.dumps(fetch_citibike(), indent=2))
    print(json.dumps(fetch_air_quality(), indent=2))
