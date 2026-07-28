#!/usr/bin/env bash
# One-shot: make /opt/ai-site-agent writable for local WSL deploys as $USER.
# Usage: sudo bash deploy/fix-opt-permissions.sh
set -euo pipefail

TARGET="${PROJECT_ROOT:-/opt/ai-site-agent}"
OWNER="${SUDO_USER:-${1:-$USER}}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash $0" >&2
  exit 1
fi

if [[ ! -d "$TARGET" ]]; then
  echo "Missing $TARGET" >&2
  exit 1
fi

echo "chown -R ${OWNER}:${OWNER} $TARGET"
chown -R "${OWNER}:${OWNER}" "$TARGET"
# u+rwX for owner; g+rwX for group; o+rx on dirs so path traversal works if
# systemd User differs briefly, and avoid status=200/CHDIR on 700 trees.
chmod -R u+rwX,g+rwX "$TARGET"
chmod u+rwx,g+rx,o+rx "$TARGET"
find "$TARGET" -type d -exec chmod u+rwx,g+rx,o+rx {} +
chmod 600 "$TARGET/.env" 2>/dev/null || true
mkdir -p "$TARGET/backups" "$TARGET/logs"
chown -R "${OWNER}:${OWNER}" "$TARGET/backups" "$TARGET/logs"

# Keep deploy config aligned for this machine.
CONF="$TARGET/deploy/deploy.local.conf"
if [[ -f "$CONF" ]]; then
  sed -i 's/^APP_USER=.*/APP_USER="'"$OWNER"'"/' "$CONF"
  sed -i 's/^APP_GROUP=.*/APP_GROUP="'"$OWNER"'"/' "$CONF"
  echo "Updated APP_USER/APP_GROUP in $CONF → $OWNER"
fi

touch "$TARGET/backups/.write_test"
rm -f "$TARGET/backups/.write_test"
echo "OK: $TARGET is writable by $OWNER"
