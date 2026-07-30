#!/usr/bin/env bash
# Regression: deploy rsync must never overwrite runtime secrets or local state.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/deploy/manage_deploy.sh"
ONCE="$ROOT/scripts/run_postgres_migration_once.sh"

if [[ ! -f "$SCRIPT" ]]; then
  echo "FAIL: missing $SCRIPT" >&2
  exit 1
fi
if [[ ! -f "$ONCE" ]]; then
  echo "FAIL: missing $ONCE" >&2
  exit 1
fi

REQUIRED=(
  "exclude '.env'"
  "exclude '.env.*'"
  "exclude 'backups/'"
  "exclude 'logs/'"
  "exclude 'deployments/'"
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

# Both production sync paths (dev-checkout + staging) must protect runtime state.
for pattern in "exclude '.env'" "exclude 'deployments/'"; do
  count=$(grep -Fc -- "$pattern" "$SCRIPT" || true)
  if [[ "$count" -lt 2 ]]; then
    echo "FAIL: expected $pattern in both sync_from_dev_checkout and staging rsync (found $count)" >&2
    exit 1
  fi
done

if ! grep -Fq -- "exclude 'deployments/'" "$ONCE"; then
  echo "FAIL: $ONCE missing rsync exclude 'deployments/'" >&2
  exit 1
fi

# Behavioral: --delete must not remove destination deployments/ when excluded.
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/src/app" "$tmp/dst/deployments/migration" "$tmp/dst/obsolete"
echo keep > "$tmp/dst/deployments/migration/state.json"
echo gone > "$tmp/dst/obsolete/stale.txt"
echo new > "$tmp/src/app/file.txt"

rsync -a --delete \
  --exclude 'deployments/' \
  "$tmp/src/" "$tmp/dst/"

[[ -f "$tmp/dst/deployments/migration/state.json" ]] || {
  echo "FAIL: excluded deployments/ was deleted by rsync --delete" >&2
  exit 1
}
[[ -f "$tmp/dst/app/file.txt" ]] || {
  echo "FAIL: application file was not synced" >&2
  exit 1
}
[[ ! -e "$tmp/dst/obsolete/stale.txt" ]] || {
  echo "FAIL: obsolete application file outside excluded dirs was not deleted" >&2
  exit 1
}

echo "OK: deploy rsync excludes .env, backups, logs, deployments/, and local DB artifacts"
