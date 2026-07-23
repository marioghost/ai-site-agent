#!/usr/bin/env bash
# Fix dev checkout ownership so your user (and Cursor) can edit files.
# Run: sudo bash scripts/fix-dev-permissions.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"

if [[ "$EUID" -ne 0 ]]; then
  echo "Run with sudo: sudo bash $0" >&2
  exit 1
fi

chown -R "${USER_NAME}:${USER_NAME}" "$REPO"
echo "Ownership set to ${USER_NAME} for $REPO"
