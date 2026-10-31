#!/usr/bin/env bash
# Launch Chromium full screen against the local dashboard.
set -euo pipefail

URL="http://127.0.0.1:8080"

# Wait for the Flask app to answer before opening the browser, otherwise
# Chromium caches an error page and sits on it forever.
for _ in $(seq 1 60); do
  curl -sf "$URL/healthz" >/dev/null && break
  sleep 2
done

# Keep the screen awake. X11 first, then Wayland.
if [ "${XDG_SESSION_TYPE:-}" = "x11" ]; then
  xset s off -dpms s noblank || true
else
  command -v wlopm >/dev/null && wlopm --on '*' || true
fi

exec chromium-browser \
  --kiosk \
  --app="$URL" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate,TranslateUI \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  --start-fullscreen
