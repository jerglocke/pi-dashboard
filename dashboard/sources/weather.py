"""
Weather from Open-Meteo (current + forecast, no key, no rate limit worth
worrying about) and severe-weather alerts from the National Weather Service.
"""
from __future__ import annotations

from datetime import datetime

import requests

import config

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
NWS_ALERTS = "https://api.weather.gov/alerts/active"

# WMO weather interpretation codes -> (short label, glyph)
WMO = {
    0: ("Clear", "\u2600"),
    1: ("Mostly clear", "\u2600"),
    2: ("Partly cloudy", "\u26c5"),
    3: ("Overcast", "\u2601"),
    45: ("Fog", "\u2591"), 48: ("Freezing fog", "\u2591"),
    51: ("Light drizzle", "\u2602"), 53: ("Drizzle", "\u2602"),
    55: ("Heavy drizzle", "\u2602"),
    56: ("Freezing drizzle", "\u2602"), 57: ("Freezing drizzle", "\u2602"),
    61: ("Light rain", "\u2602"), 63: ("Rain", "\u2602"),
    65: ("Heavy rain", "\u2602"),
    66: ("Freezing rain", "\u2602"), 67: ("Freezing rain", "\u2602"),
    71: ("Light snow", "\u2744"), 73: ("Snow", "\u2744"),
    75: ("Heavy snow", "\u2744"), 77: ("Snow grains", "\u2744"),
    80: ("Showers", "\u2602"), 81: ("Showers", "\u2602"),
    82: ("Downpours", "\u2602"),
    85: ("Snow showers", "\u2744"), 86: ("Snow showers", "\u2744"),
    95: ("Thunderstorms", "\u26a1"),
    96: ("Storms, hail", "\u26a1"), 99: ("Storms, hail", "\u26a1"),
}


def describe(code: int) -> tuple[str, str]:
    return WMO.get(code, ("--", ""))


def _alerts() -> list[dict]:
    """Active NWS watches/warnings for this exact point. Usually empty."""
    try:
        resp = requests.get(
            NWS_ALERTS,
            params={"point": f"{config.LATITUDE},{config.LONGITUDE}"},
            headers={"User-Agent": config.USER_AGENT, "Accept": "application/geo+json"},
            timeout=10,
        )
        resp.raise_for_status()
        out = []
        for feature in resp.json().get("features", []):
            props = feature.get("properties", {})
            if props.get("severity") in ("Minor", "Unknown"):
                continue
            out.append({
                "headline": props.get("event", "Weather alert"),
                "severity": props.get("severity", ""),
            })
        return out[:2]
    except requests.RequestException:
        return []


def fetch() -> dict:
    resp = requests.get(
        OPEN_METEO,
        params={
            "latitude": config.LATITUDE,
            "longitude": config.LONGITUDE,
            "current": "temperature_2m,apparent_temperature,weather_code,"
                       "relative_humidity_2m,wind_speed_10m",
            "hourly": "temperature_2m,precipitation_probability,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,sunrise,sunset",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "America/New_York",
            "forecast_days": getattr(config, "FORECAST_DAYS", 3) + 1,
        },
        timeout=12,
    )
    resp.raise_for_status()
    data = resp.json()

    cur = data["current"]
    label, glyph = describe(cur["weather_code"])

    # Next few hours, so you know whether to grab a jacket on the way out.
    hours = []
    now_iso = datetime.now(config.TIMEZONE).strftime("%Y-%m-%dT%H:00")
    h = data["hourly"]
    try:
        start = h["time"].index(now_iso) + 1
    except ValueError:
        start = 1
    for i in range(start, min(start + 6, len(h["time"]))):
        hours.append({
            "hour": datetime.fromisoformat(h["time"][i]).strftime("%-I%p").lower(),
            "temp": round(h["temperature_2m"][i]),
            "precip": h["precipitation_probability"][i],
            "glyph": describe(h["weather_code"][i])[1],
        })

    days = []
    d = data["daily"]
    wanted = getattr(config, "FORECAST_DAYS", 3)
    for i in range(1, min(len(d["time"]), wanted + 1)):
        day_label, day_glyph = describe(d["weather_code"][i])
        days.append({
            "name": datetime.fromisoformat(d["time"][i]).strftime("%a"),
            "high": round(d["temperature_2m_max"][i]),
            "low": round(d["temperature_2m_min"][i]),
            "precip": d["precipitation_probability_max"][i],
            "glyph": day_glyph,
            "label": day_label,
        })

    return {
        "temp": round(cur["temperature_2m"]),
        "feels_like": round(cur["apparent_temperature"]),
        "humidity": cur["relative_humidity_2m"],
        "wind": round(cur["wind_speed_10m"]),
        "label": label,
        "glyph": glyph,
        "sunrise": datetime.fromisoformat(d["sunrise"][0]).strftime("%-I:%M"),
        "sunset": datetime.fromisoformat(d["sunset"][0]).strftime("%-I:%M"),
        "hours": hours,
        "days": days,
        "alerts": _alerts(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), indent=2))
