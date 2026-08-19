#!/usr/bin/env bash
set -euo pipefail

# Installs and enables boat.service and boat-updater.service/.timer.
# Run from the project root on the Raspberry Pi: sudo deploy/install.sh

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="/etc/systemd/system"

if [[ $EUID -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

for unit in boat.service boat-updater.service boat-updater.timer; do
  echo "Installing $unit"
  cp "$PROJECT_ROOT/deploy/$unit" "$UNIT_DIR/$unit"
done

systemctl daemon-reload
systemctl enable --now boat.service
systemctl enable --now boat-updater.timer

cat <<'EOF'

Done. Remember:
  1. Edit /etc/systemd/system/boat.service and boat-updater.service if the
     project path or user differs from the defaults (WorkingDirectory, ExecStart, User).
  2. The updater needs passwordless sudo to restart boat.service. Add a line like this
     via `sudo visudo -f /etc/sudoers.d/boat-updater` (replace <user> with the service user):

       <user> ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart boat.service

  3. Copy .env.example to .env and fill in real values before starting the service.
EOF
