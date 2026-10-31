"""
Your overrides. Copy to local_settings.py -- that file is never shipped in an
update, so anything you set here survives every upgrade.

Any name from config.py can be overridden. These are the ones people change.
"""

# Serve on the network so you can check the board from a laptop or phone.
HOST = "0.0.0.0"

# Minutes from your door to the platform. Decides which trains show as
# reachable, so measure it once rather than guessing.
WALK_MINUTES = 5

# Swap a dead feed without editing config.py:
# NEWS_FEEDS = [
#     {"name": "Gothamist",     "section": "nyc",      "url": "https://gothamist.com/feed"},
#     {"name": "The City",      "section": "nyc",      "url": "https://www.thecity.nyc/feed/"},
#     {"name": "Brooklyn Paper","section": "nyc",      "url": "https://www.brooklynpaper.com/feed/"},
#     {"name": "NPR",           "section": "national", "url": "https://feeds.npr.org/1001/rss.xml"},
#     {"name": "PBS NewsHour",  "section": "national", "url": "https://www.pbs.org/newshour/feeds/rss/headlines"},
# ]
