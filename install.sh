#!/usr/bin/env bash
#
# Install or update the dashboard. Safe to run repeatedly -- it is the update
# path as well as the first install. Run it from inside ~/pi-dashboard:
#
#     bash install.sh
#
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

say "Stopping services"
systemctl --user stop kiosk dashboard 2>/dev/null || true

say "Python environment"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
echo "dependencies installed"

say "Local settings"
if [ ! -f local_settings.py ]; then
  cp local_settings.example.py local_settings.py
  echo "created local_settings.py -- put HOST, WALK_MINUTES etc. in there."
  echo "it is never overwritten by an update."
else
  echo "local_settings.py already present, left alone"
fi
[ -f .env ] || { cp .env.example .env; echo "created .env -- add your iCloud credentials"; }

say "Services"
chmod +x deploy/kiosk.sh
mkdir -p "$HOME/.config/systemd/user"
cp deploy/dashboard.service deploy/kiosk.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable dashboard kiosk >/dev/null 2>&1 || true
sudo loginctl enable-linger "$USER" 2>/dev/null || true

say "Starting"
systemctl --user start dashboard
printf 'waiting for the board to render'
ok=""
for _ in $(seq 1 40); do
  if curl -sf localhost:8080/healthz 2>/dev/null | grep -q '"renders": *true'; then
    ok=yes; break
  fi
  printf '.'; sleep 2
done
echo

if [ -z "$ok" ]; then
  echo "The page is NOT rendering. The reason:"
  journalctl --user -u dashboard -n 30 --no-pager | tail -20
  echo
  echo "Fix the above, then run: systemctl --user restart dashboard"
  exit 1
fi

systemctl --user start kiosk
say "Done"
curl -s localhost:8080/healthz
echo
echo "The board should be on the screen. Useful commands:"
echo "  systemctl --user stop kiosk       # get the desktop back"
echo "  systemctl --user restart kiosk    # put the board back"
echo "  curl -s localhost:8080/healthz    # what is working"
