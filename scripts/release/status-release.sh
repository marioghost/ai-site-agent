#!/usr/bin/env bash
# Concise release/deploy status — repository → /opt → runtime identity.
# Usage: bash deploy/manage_deploy.sh status
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib/deploy_guard.sh
source "$ROOT/deploy/lib/deploy_guard.sh"
# shellcheck source=scripts/lib/deploy-env.sh
source "$ROOT/scripts/lib/deploy-env.sh" 2>/dev/null || true

PROJECT_ROOT="${PROJECT_ROOT:-/opt/ai-site-agent}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/api/health}"
BUILD_URL="${HEALTHCHECK_URL%/api/health}/api/build"
OVERVIEW_URL="${HEALTHCHECK_URL%/api/health}/api/overview"

overall="OK"
note() { printf "  %-18s %s\n" "$1" "$2"; }
fail_mark() { overall="NOT OK"; }

deploy_guard_fetch_origin "$ROOT" 2>/dev/null || true
BRANCH="$(git -C "$ROOT" symbolic-ref -q HEAD 2>/dev/null | sed 's|^refs/heads/||' || echo DETACHED)"
HEAD="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo "?")"
HEAD_FULL="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo "?")"
LOCAL_MAIN="$(deploy_guard_local_main_hash "$ROOT" 2>/dev/null || echo "?")"
ORIGIN_MAIN="$(deploy_guard_origin_main_hash "$ROOT" 2>/dev/null || echo "?")"
LOCAL_SHORT="$(git -C "$ROOT" rev-parse --short "$LOCAL_MAIN" 2>/dev/null || echo "?")"
ORIGIN_SHORT="$(git -C "$ROOT" rev-parse --short "$ORIGIN_MAIN" 2>/dev/null || echo "?")"
CLEAN="dirty"
deploy_guard_is_clean_worktree "$ROOT" && CLEAN="clean"

echo "=== manage_deploy status ==="
echo ""
echo "Repository"
note "branch:" "$BRANCH"
note "HEAD:" "$HEAD"
note "main:" "$LOCAL_SHORT"
note "origin/main:" "$ORIGIN_SHORT"
note "tree:" "$CLEAN"
if [[ "$BRANCH" != "main" ]]; then fail_mark; fi
if [[ "$CLEAN" != "clean" ]]; then fail_mark; fi
if [[ "$LOCAL_MAIN" != "$ORIGIN_MAIN" ]]; then fail_mark; fi

echo ""
echo "Deployment (/opt)"
BUILD_FILE="$PROJECT_ROOT/.build-info.json"
FE_ID="$PROJECT_ROOT/dashboard/dist/.deploy-identity.json"
DEP_COMMIT="?"
DEP_RELEASE="?"
FE_COMMIT="?"
if [[ -f "$BUILD_FILE" ]]; then
  DEP_COMMIT="$(python3 -c "import json; print(json.load(open('$BUILD_FILE')).get('git_commit','?'))" 2>/dev/null || echo "?")"
  DEP_RELEASE="$(python3 -c "import json; print(json.load(open('$BUILD_FILE')).get('release','?'))" 2>/dev/null || echo "?")"
fi
if [[ -f "$FE_ID" ]]; then
  FE_COMMIT="$(python3 -c "import json; print(json.load(open('$FE_ID')).get('git_commit','?'))" 2>/dev/null || echo "?")"
fi
APP_REL="$(deploy_guard_read_app_release "$ROOT" 2>/dev/null || echo "?")"
note "build-info:" "${DEP_COMMIT:0:12}  release=$DEP_RELEASE"
note "frontend:" "${FE_COMMIT:0:12}"
note "APP_RELEASE:" "$APP_REL"
note "dist:" "$([[ -f $PROJECT_ROOT/dashboard/dist/index.html ]] && echo present || echo MISSING)"
if [[ "$DEP_COMMIT" != "$ORIGIN_MAIN" ]]; then fail_mark; fi
if [[ "$FE_COMMIT" != "$DEP_COMMIT" && "$FE_COMMIT" != "?" ]]; then fail_mark; fi
if [[ "$DEP_RELEASE" != "?" && "$APP_REL" != "?" && "$DEP_RELEASE" != "$APP_REL" ]]; then fail_mark; fi
if [[ ! -f "$PROJECT_ROOT/dashboard/dist/index.html" ]]; then fail_mark; fi

echo ""
echo "Runtime"
API_COMMIT="?"
API_RELEASE="?"
ALEMBIC="?"
FLAGS=""
if curl -sf --max-time 4 "$HEALTHCHECK_URL" >/dev/null 2>&1; then
  note "health:" "UP"
else
  note "health:" "DOWN"
  fail_mark
fi
if curl -sf --max-time 4 "$BUILD_URL" -o /tmp/md-status-build.json 2>/dev/null; then
  API_COMMIT="$(python3 -c "import json; print(json.load(open('/tmp/md-status-build.json')).get('git_commit') or '?')" 2>/dev/null || echo "?")"
  API_RELEASE="$(python3 -c "import json; print(json.load(open('/tmp/md-status-build.json')).get('release') or '?')" 2>/dev/null || echo "?")"
  ALEMBIC="$(python3 -c "import json; print(json.load(open('/tmp/md-status-build.json')).get('alembic_head') or '?')" 2>/dev/null || echo "?")"
  FLAGS="$(python3 - <<'PY' 2>/dev/null || true
import json
d=json.load(open("/tmp/md-status-build.json"))
flags=d.get("feature_flags") or {}
# compact: only non-default / interesting flags
keys=["memory_evidence_assist_enabled","memory_canonical_shadow_enabled","cache_namespace_v2_enabled","memory_shadow_write_enabled","REASONING_SERVICE_ENABLED"]
parts=[]
for k in keys:
    if k in flags:
        parts.append(f"{k}={'ON' if flags[k] else 'off'}")
print(", ".join(parts) if parts else "n/a")
PY
)"
  note "api build:" "${API_COMMIT:0:12}  release=$API_RELEASE"
  note "migrations:" "$ALEMBIC"
  note "flags:" "${FLAGS:-n/a}"
  if [[ "$API_COMMIT" != "$DEP_COMMIT" ]]; then fail_mark; fi
  if [[ "$API_COMMIT" != "$ORIGIN_MAIN" ]]; then fail_mark; fi
else
  note "api build:" "unreachable"
  fail_mark
fi

echo ""
echo "Corpus / Qdrant"
if curl -sf --max-time 4 "$OVERVIEW_URL" -o /tmp/md-status-overview.json 2>/dev/null; then
  python3 - <<'PY' 2>/dev/null | while IFS= read -r line; do note "overview:" "$line"; done || note "overview:" "present"
import json
d=json.load(open("/tmp/md-status-overview.json"))
interesting=[]
for k in ("sources_count","chunks_count","claims_count","knowledge_version","memory_version","qdrant_points"):
    if k in d: interesting.append(f"{k}={d[k]}")
# nested common shapes
for nest in ("stats","counts","corpus","metrics"):
    if isinstance(d.get(nest), dict):
        for k,v in list(d[nest].items())[:8]:
            interesting.append(f"{nest}.{k}={v}")
print(", ".join(interesting[:10]) if interesting else "keys present")
PY
else
  note "overview:" "unreachable (auth/down)"
fi
if curl -sf --max-time 3 "http://127.0.0.1:6333/collections" >/dev/null 2>&1; then
  note "qdrant:" "UP"
else
  note "qdrant:" "DOWN/unreachable"
fi

echo ""
echo "Overall: $overall"
if [[ "$overall" != "OK" ]]; then
  exit 1
fi
exit 0
