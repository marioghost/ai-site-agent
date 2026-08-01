#!/usr/bin/env bash
# Shared release verification core (One Command Deployment).
# Used by: deploy full (hard gate) and standalone verify-release (diagnostics).
set -euo pipefail

md_verify_release_run() {
  local root="${1:-}"
  local project_root="${2:-}"
  local expected_commit="${3:-}"
  local expected_release="${4:-}"

  if [[ -z "$root" ]]; then
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  fi
  # shellcheck source=deploy/lib/deploy_guard.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy_guard.sh"

  project_root="${project_root:-${PROJECT_ROOT:-/opt/ai-site-agent}}"
  local healthcheck_url="${HEALTHCHECK_URL:-http://127.0.0.1:8000/api/health}"
  local build_url="${healthcheck_url%/api/health}/api/build"
  local overview_url="${healthcheck_url%/api/health}/api/overview"

  local PASS=0 FAIL=0 WARN=0
  ok() { echo "  PASS  $*"; PASS=$((PASS + 1)); }
  bad() { echo "  FAIL  $*"; FAIL=$((FAIL + 1)); }
  warn() { echo "  WARN  $*"; WARN=$((WARN + 1)); }
  section() { echo ""; echo "=== $* ==="; }

  section "Release verification"
  echo "Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Repo: $root"
  echo "Deploy root: $project_root"

  section "1. Repository (operator checkout)"
  deploy_guard_fetch_origin "$root" || true
  local BRANCH HEAD LOCAL_MAIN ORIGIN_MAIN
  BRANCH="$(git -C "$root" symbolic-ref -q HEAD 2>/dev/null | sed 's|^refs/heads/||' || echo DETACHED)"
  HEAD="$(git -C "$root" rev-parse HEAD 2>/dev/null || echo unknown)"
  LOCAL_MAIN="$(deploy_guard_local_main_hash "$root" 2>/dev/null || echo unknown)"
  ORIGIN_MAIN="$(deploy_guard_origin_main_hash "$root" 2>/dev/null || echo unknown)"
  if [[ -n "$expected_commit" ]]; then
    ORIGIN_MAIN="$expected_commit"
  fi
  echo "  branch:      $BRANCH"
  echo "  HEAD:        $HEAD"
  echo "  local main:  $LOCAL_MAIN"
  echo "  origin/main: $ORIGIN_MAIN"
  if [[ -n "$expected_commit" ]]; then
    ok "expected deploy tip $expected_commit"
  else
    if [[ "$BRANCH" == "main" ]]; then ok "on main"; else bad "not on main ($BRANCH)"; fi
    if [[ "$BRANCH" != "DETACHED" ]]; then ok "not detached"; else bad "detached HEAD"; fi
    if deploy_guard_is_clean_worktree "$root"; then ok "clean working tree"; else bad "dirty working tree"; fi
    if [[ "$LOCAL_MAIN" == "$ORIGIN_MAIN" && "$LOCAL_MAIN" != "unknown" ]]; then
      ok "local main == origin/main"
    else
      bad "local main != origin/main"
    fi
  fi

  section "2. Build identity on disk ($project_root)"
  local BUILD_FILE FE_ID DEPLOYED_COMMIT FE_COMMIT=""
  BUILD_FILE="$project_root/.build-info.json"
  FE_ID="$project_root/dashboard/dist/.deploy-identity.json"
  DEPLOYED_COMMIT=""
  if [[ -f "$BUILD_FILE" ]]; then
    DEPLOYED_COMMIT="$(python3 -c "import json; print(json.load(open('$BUILD_FILE')).get('git_commit',''))" 2>/dev/null || echo "")"
    python3 -m json.tool "$BUILD_FILE" | sed 's/^/  /'
    if [[ -n "$DEPLOYED_COMMIT" ]]; then ok "build-info present ($DEPLOYED_COMMIT)"; else bad "build-info missing git_commit"; fi
  else
    bad "missing $BUILD_FILE"
  fi
  if [[ -n "$DEPLOYED_COMMIT" && "$DEPLOYED_COMMIT" == "$ORIGIN_MAIN" ]]; then
    ok "build-info == origin/main (tip)"
  else
    bad "build-info ($DEPLOYED_COMMIT) != tip ($ORIGIN_MAIN)"
  fi
  if [[ -f "$FE_ID" ]]; then
    FE_COMMIT="$(python3 -c "import json; print(json.load(open('$FE_ID')).get('git_commit',''))" 2>/dev/null || echo "")"
    echo "  frontend identity: $FE_COMMIT"
    if [[ "$FE_COMMIT" == "$DEPLOYED_COMMIT" && -n "$FE_COMMIT" ]]; then
      ok "frontend identity matches build-info"
    else
      bad "frontend/backend identity mismatch ($FE_COMMIT vs $DEPLOYED_COMMIT)"
    fi
  else
    bad "missing frontend identity $FE_ID"
  fi
  if [[ -f "$project_root/dashboard/dist/index.html" ]]; then
    ok "frontend dist present"
  else
    bad "frontend dist missing"
  fi

  section "3. Runtime health + /api/build"
  local API_COMMIT="" API_RELEASE="" ALEMBIC=""
  if curl -sf --max-time 5 "$healthcheck_url" -o /tmp/vr-health.json 2>/dev/null; then
    ok "health OK ($healthcheck_url)"
  else
    bad "health unreachable ($healthcheck_url)"
  fi
  if curl -sf --max-time 5 "$build_url" -o /tmp/vr-build.json 2>/dev/null; then
    API_COMMIT="$(python3 -c "import json; print(json.load(open('/tmp/vr-build.json')).get('git_commit') or '')" 2>/dev/null || echo "")"
    API_RELEASE="$(python3 -c "import json; print(json.load(open('/tmp/vr-build.json')).get('release') or '')" 2>/dev/null || echo "")"
    ALEMBIC="$(python3 -c "import json; print(json.load(open('/tmp/vr-build.json')).get('alembic_head') or '')" 2>/dev/null || echo "")"
    echo "  api release: $API_RELEASE"
    echo "  api commit:  $API_COMMIT"
    echo "  alembic:     $ALEMBIC"
    if [[ -n "$API_COMMIT" && "$API_COMMIT" == "$DEPLOYED_COMMIT" ]]; then
      ok "/api/build matches build-info"
    else
      bad "/api/build ($API_COMMIT) != build-info ($DEPLOYED_COMMIT)"
    fi
    if [[ -n "$API_COMMIT" && "$API_COMMIT" == "$ORIGIN_MAIN" ]]; then
      ok "/api/build matches tip"
    else
      bad "/api/build ($API_COMMIT) != tip ($ORIGIN_MAIN)"
    fi
    if [[ -n "$expected_release" ]]; then
      if [[ "$API_RELEASE" == "$expected_release" ]]; then
        ok "/api/build release == tip APP_RELEASE ($expected_release)"
      else
        bad "/api/build release ($API_RELEASE) != tip APP_RELEASE ($expected_release)"
      fi
    fi
    python3 - <<'PY' 2>/dev/null | sed 's/^/  /' || true
import json
d=json.load(open("/tmp/vr-build.json"))
flags=d.get("feature_flags") or d.get("settings_flags") or {}
for k in sorted(flags):
    print(f"flag {k}={flags[k]}")
rs=d.get("release_status") or {}
print(f"accepted={rs.get('accepted')} staging_validated={rs.get('staging_validated')} production_ready={rs.get('production_ready')}")
PY
    ok "feature flags reported (not asserting ON)"
  else
    bad "/api/build unreachable"
  fi

  section "4. Migrations / corpus / Qdrant (best-effort)"
  if [[ -n "${ALEMBIC:-}" ]]; then
    ok "alembic_head from API: $ALEMBIC"
  else
    warn "alembic_head unavailable"
  fi
  if curl -sf --max-time 5 "$overview_url" -o /tmp/vr-overview.json 2>/dev/null; then
    ok "overview reachable (corpus snapshot best-effort)"
  else
    warn "overview unreachable (auth may be required) — skipped corpus counts"
  fi
  if curl -sf --max-time 3 "http://127.0.0.1:6333/collections" -o /tmp/vr-qdrant.json 2>/dev/null; then
    ok "Qdrant reachable"
  else
    warn "Qdrant unreachable on :6333"
  fi

  section "5. Chain summary"
  echo "  tip         : $ORIGIN_MAIN"
  echo "  build-info  : $DEPLOYED_COMMIT"
  echo "  frontend    : ${FE_COMMIT:-missing}"
  echo "  /api/build  : ${API_COMMIT:-unreachable}"
  if [[ -n "$ORIGIN_MAIN" && "$ORIGIN_MAIN" == "$DEPLOYED_COMMIT" && "$DEPLOYED_COMMIT" == "${API_COMMIT:-}" && "$DEPLOYED_COMMIT" == "${FE_COMMIT:-}" ]]; then
    ok "FULL CHAIN ALIGNED (tip == build-info == frontend == /api/build)"
  else
    bad "CHAIN BROKEN — commits do not all match"
  fi

  section "Result"
  echo "  PASS=$PASS FAIL=$FAIL WARN=$WARN"
  if [[ "$FAIL" -gt 0 ]]; then
    echo "VERDICT: FAIL"
    return 1
  fi
  echo "VERDICT: PASS"
  return 0
}
