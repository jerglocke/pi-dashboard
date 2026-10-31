"""
Configuration for the wall dashboard.

Secrets come from environment variables (see .env.example), everything else
lives here. Edit freely -- this file is meant to be tweaked.
"""
import os
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------- location --
# Prospect Lefferts Gardens, Brooklyn (Sterling St & Nostrand Ave).
LATITUDE = 40.6627
LONGITUDE = -73.9509
TIMEZONE = ZoneInfo("America/New_York")

# NWS asks that you identify yourself. Put a real email here.
USER_AGENT = os.environ.get("USER_AGENT", "pi-wall-dashboard (you@example.com)")

# ----------------------------------------------------------------- subway ---
# GTFS stop for Sterling St on the IRT Nostrand Ave Line. Platform suffixes:
#   242N -> uptown / Manhattan-bound
#   242S -> downtown / Flatbush Av-Brooklyn College
# Find other stations with:  python -m dashboard.sources.subway --find "Winthrop"
SUBWAY_STOP = "242"

# Which platforms to show, and what to call them on screen.
SUBWAY_DIRECTIONS = [
    {"platform": "242N", "label": "Manhattan"},
    {"platform": "242S", "label": "Flatbush"},
]

# The 2 and 5 both ride the numbered-lines feed.
SUBWAY_FEED = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"

# Minutes from your door to the platform. Trains you cannot physically make
# get dimmed on screen instead of taunting you.
WALK_MINUTES = 8

# How many upcoming trains to list per direction.
SUBWAY_COUNT = 5     # per direction; the two run side by side, so this can be generous

# --------------------------------------------------------------- calendar ---
# iCloud needs an app-specific password (appleid.apple.com -> Sign-In and
# Security -> App-Specific Passwords). Your normal password will not work.
ICLOUD_URL = "https://caldav.icloud.com/"
ICLOUD_USERNAME = os.environ.get("ICLOUD_USERNAME", "")
ICLOUD_PASSWORD = os.environ.get("ICLOUD_PASSWORD", "")

# Only show these calendars. Empty list = all of them.
CALENDAR_NAMES: list[str] = []

# Fallback: a published/shared .ics URL, used if no iCloud credentials are set.
ICS_URL = os.environ.get("ICS_URL", "")

CALENDAR_DAYS_AHEAD = 3
CALENDAR_MAX_EVENTS = 6

# ----------------------------------------------------------------- extras ---
CITIBIKE_STATION_COUNT = 3   # nearest N docks
SHOW_AIR_QUALITY = True

# Forecast days shown under the hourly strip. Three fits alongside an agenda
# row and two weather alerts; four only fits when the calendar is empty.
FORECAST_DAYS = 3

# ------------------------------------------------------------------- news ---
# Headlines only, from public RSS. "section" must be "nyc" or "national".
# Feeds move and die -- validate any change with:
#     python -m dashboard.sources.news --check
NEWS_FEEDS = [
    {"name": "Gothamist",  "section": "nyc",
     "url": "https://gothamist.com/feed"},
    {"name": "The City",   "section": "nyc",
     "url": "https://www.thecity.nyc/feed/"},
    {"name": "Hell Gate",  "section": "nyc",
     "url": "https://hellgatenyc.com/rss/"},
    {"name": "NPR",        "section": "national",
     "url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "PBS NewsHour", "section": "national",
     "url": "https://www.pbs.org/newshour/feeds/rss/headlines"},
]

NEWS_PER_FEED = 12   # headlines taken from each feed before merging
NEWS_POOL = 12       # headlines kept per section, cycled through on screen
# Headlines visible per section. Three total is what fits once headlines are
# allowed to wrap instead of being truncated -- a long one runs three lines,
# and four of those overflow the column. Local gets the extra slot.
NEWS_SHOWN = {"nyc": 2, "national": 1}

# ---------------------------------------------------------- on this day ----
FACT_MAX_CHARS = 140   # skip longer facts outright rather than truncating them

# ----------------------------------------------------------- rotation ------
# Both panels cycle on a shared clock rather than any stored state: the server
# derives the current item from the wall time, so every refresh agrees and
# nothing drifts. See rotate() in dashboard/app.py.
NEWS_ROTATE_SECONDS = 45
FACT_ROTATE_SECONDS = 420   # ~7 minutes

# -------------------------------------------------------------- behaviour ---
# Seconds between refreshes, per source. The browser re-polls every 15s and
# just gets whatever the cache holds.
REFRESH_SECONDS = {
    "subway": 30,
    "weather": 600,
    "calendar": 300,
    "citibike": 120,
    "airquality": 900,
    "news": 600,
    "onthisday": 3600,   # cached by date anyway; this just retries after a fail
}

HOST = "127.0.0.1"
PORT = 8080


# ---------------------------------------------------------------- local ----
# Machine-specific overrides live in local_settings.py, which is NOT part of
# the release tarball. Put HOST, WALK_MINUTES, swapped feed URLs and anything
# else you tune in there, and an update can never clobber them again.
try:
    from local_settings import *          # noqa: F401,F403
except ImportError:
    pass
