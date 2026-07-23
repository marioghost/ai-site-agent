#!/usr/bin/env bash
# Staging rollback helper for Linux server (systemd). Does NOT downgrade production DB.
#
#   ./scripts/release/rollback-staging.sh
#   ./scripts/release/rollback-staging.sh --restart-backend
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

RESTART=0
for arg in "$@"; do
  case "$arg" in
    --restart-backend) RESTART=1 ;;
  esac
done

echo "==> Staging rollback checklist (Linux server)"
cat <<'EOF'
1. Feature flags OFF (immediate, no redeploy):
   - KNOWLEDGE_OS_EXECUTIVE_ENABLED=false in .env + restart backend
   - enable_semantic_diagnostics_v2=false (Settings API)
   - cache_namespace_v2_enabled=false (Settings API)

2. Application rollback:
   - Redeploy previous git tag/commit:
       git checkout <previous-tag>
       sudo bash deploy/manage_deploy.sh --mode update --yes
   - Or restore from /tmp staging tree if used:
       bash deploy/prepare_staging.sh
       sudo bash deploy/install_from_staging.sh

3. Migration rollback policy:
   - Prefer flag OFF over Alembic downgrade in staging/production
   - Downgrade only on explicit ops approval with pg_dump backup
   - See docs/releases/0.3-rollback.md

4. Cache clear (if namespace/routing changed):
   - POST /api/settings/cache/clear-all (admin), or
   - sudo bash deploy/manage_deploy.sh --action clear-cache

5. Verify:
   - make smoke-staging
   - make test-backend (golden unit parity)
   - sudo journalctl -u ai-agent-backend -n 100 --no-pager
EOF

if [[ "$RESTART" -eq 1 ]]; then
  echo "==> Restart backend service"
  if [[ "$(id -u)" -eq 0 ]]; then
    systemctl restart ai-agent-backend
  elif command -v sudo &>/dev/null; then
    sudo systemctl restart ai-agent-backend
  else
    echo "WARN: cannot restart — run as root or with sudo" >&2
    exit 1
  fi
  echo "OK: ai-agent-backend restarted"
fi

echo "OK: rollback checklist printed"
