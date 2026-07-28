#!/usr/bin/env bash
# Regression: deploy rsync must never overwrite runtime secrets or local state.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/deploy/manage_deploy.sh"

if [[ ! -f "$SCRIPT" ]]; then
  echo "FAIL: missing $SCRIPT" >&2
  exit 1
fi

REQUIRED=(
  "exclude '.env'"
  "exclude '.env.*'"
  "exclude 'backups/'"
  "exclude 'logs/'"
  "exclude 'backend/ai_site_agent.db'"
  "exclude 'backend/ai_site_agent.db-*'"
)

missing=()
for pattern in "${REQUIRED[@]}"; do
  if ! grep -Fq -- "$pattern" "$SCRIPT"; then
    missing+=("$pattern")
  fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "FAIL: deploy/manage_deploy.sh missing rsync excludes:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

# Both dev-checkout and staging sync paths must protect .env.
env_exclude_count=$(grep -Fc "exclude '.env'" "$SCRIPT" || true)
if [[ "$env_exclude_count" -lt 2 ]]; then
  echo "FAIL: expected .env exclude in both sync_from_dev_checkout and staging rsync (found $env_exclude_count)" >&2
  exit 1
fi

echo "OK: deploy rsync excludes .env, backups, logs, and local DB artifacts"
