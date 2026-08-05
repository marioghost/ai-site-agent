#!/usr/bin/env bash
# Shared release verification core (One Command Deployment).
# Used by: deploy full (hard gate) and standalone verify-release (diagnostics).
# Phase 2: Part 3/4 served FE provenance + mode-aware FE rules + writable temps.
set -euo pipefail

# Mode-aware served frontend tree check (amendment Part 3 + Part 4 / Phase 2 package §4.1).
# Inputs: project_root, mode (full|frontend|backend|standalone), tip_commit
# Uses ok/bad from caller scope when available; otherwise echoes PASS/FAIL lines.
md_verify_frontend_served_tree() {
  local project_root="$1"
  local mode="$2"
  local tip_commit="$3"
  local dist="$project_root/dashboard/dist"
  local prov="$dist/.frontend-provenance.json"
  local ident="$dist/.deploy-identity.json"
  local build_file="$project_root/.build-info.json"
  # Prefer caller's ok/bad (counts FAIL); fall back for standalone unit use.
  if ! declare -F ok >/dev/null 2>&1; then
    ok() { echo "  PASS  $*"; }
  fi
  if ! declare -F bad >/dev/null 2>&1; then
    bad() { echo "  FAIL  $*"; }
  fi

  if [[ ! -f "$prov" ]]; then
    bad "missing frontend provenance $prov"
    return 1
  fi
  if [[ ! -f "$ident" ]]; then
    bad "missing frontend identity $ident"
    return 1
  fi

  # Part 3 hashing/orphans/tree (no tip expected yet).
  if ! deploy_guard_assert_frontend_provenance "$dist"; then
    bad "frontend provenance verification failed ($dist)"
    return 1
  fi
  ok "frontend provenance Part 3 PASS ($dist)"

  local fe_id fe_prov tree_id tree_prov bi_fe
  fe_id="$(python3 -c "import json; print(json.load(open('$ident')).get('git_commit') or '')" 2>/dev/null || echo "")"
  fe_prov="$(python3 -c "import json; print(json.load(open('$prov')).get('git_commit') or '')" 2>/dev/null || echo "")"
  tree_id="$(python3 -c "import json; print(json.load(open('$ident')).get('provenance_tree_sha256') or '')" 2>/dev/null || echo "")"
  tree_prov="$(python3 -c "import json; print(json.load(open('$prov')).get('tree_sha256') or '')" 2>/dev/null || echo "")"
  bi_fe=""
  if [[ -f "$build_file" ]]; then
    bi_fe="$(python3 -c "import json; print(json.load(open('$build_file')).get('frontend_commit') or '')" 2>/dev/null || echo "")"
  fi

  if [[ -z "$fe_id" || -z "$fe_prov" || "$fe_id" != "$fe_prov" ]]; then
    bad "frontend identity git_commit ($fe_id) != provenance git_commit ($fe_prov)"
    return 1
  fi
  ok "frontend identity commit matches provenance ($fe_id)"

  if [[ -z "$tree_id" || -z "$tree_prov" || "$tree_id" != "$tree_prov" ]]; then
    bad "identity provenance_tree_sha256 ($tree_id) != provenance tree_sha256 ($tree_prov)"
    return 1
  fi
  ok "identity provenance_tree_sha256 matches provenance tree_sha256"

  case "$mode" in
    full|frontend|standalone|"")
      if [[ -z "$tip_commit" || "$fe_id" != "$tip_commit" ]]; then
        bad "frontend identity ($fe_id) != tip ($tip_commit)"
        return 1
      fi
      ok "frontend identity matches tip ($tip_commit)"
      if [[ -z "$bi_fe" || "$bi_fe" != "$tip_commit" ]]; then
        bad "build-info frontend_commit ($bi_fe) != tip ($tip_commit)"
        return 1
      fi
      ok "build-info frontend_commit matches tip"
      ;;
    backend)
      if [[ -z "$bi_fe" || "$bi_fe" != "$fe_id" ]]; then
        bad "build-info frontend_commit ($bi_fe) != preserved FE identity ($fe_id)"
        return 1
      fi
      ok "backend mode: frontend_commit matches preserved FE identity ($fe_id)"
      if [[ -n "$tip_commit" && "$fe_id" != "$tip_commit" ]]; then
        ok "backend mode: FE lag allowed (FE=$fe_id tip=$tip_commit)"
      fi
      ;;
    *)
      bad "unknown verify mode: $mode"
      return 1
      ;;
  esac
  return 0
}

md_verify_release_run() {
  local root="${1:-}"
  local project_root="${2:-}"
  local expected_commit="${3:-}"
  local expected_release="${4:-}"
  local verify_mode="${5:-${MD_VERIFY_MODE:-standalone}}"

  if [[ -z "$root" ]]; then
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  fi
  # shellcheck source=deploy/lib/deploy_guard.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy_guard.sh"

  project_root="${project_root:-${PROJECT_ROOT:-/opt/ai-site-agent}}"
  local healthcheck_url="${HEALTHCHECK_URL:-http://127.0.0.1:8000/api/health}"
  local build_url="${healthcheck_url%/api/health}/api/build"
  local overview_url="${healthcheck_url%/api/health}/api/overview"

  # Phase 2 E — writable unique temp workspace (no fixed /tmp/vr-*.json).
  # Use RETURN trap so we do not clobber deploy_source EXIT cleanup.
  local VR_TMP
  VR_TMP="$(mktemp -d /tmp/ai-site-agent-vr-XXXXXX)"
  # shellcheck disable=SC2064
  trap "rm -rf -- '${VR_TMP}'" RETURN

  local PASS=0 FAIL=0 WARN=0
  ok() { echo "  PASS  $*"; PASS=$((PASS + 1)); }
  bad() { echo "  FAIL  $*"; FAIL=$((FAIL + 1)); }
  warn() { echo "  WARN  $*"; WARN=$((WARN + 1)); }
  section() { echo ""; echo "=== $* ==="; }

  section "Release verification"
  echo "Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Repo: $root"
  echo "Deploy root: $project_root"
  echo "Verify mode: $verify_mode"

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
  local BUILD_FILE FE_ID DEPLOYED_COMMIT FE_COMMIT="" BACKEND_COMMIT="" FRONTEND_COMMIT_BI=""
  BUILD_FILE="$project_root/.build-info.json"
  FE_ID="$project_root/dashboard/dist/.deploy-identity.json"
  DEPLOYED_COMMIT=""
  if [[ -f "$BUILD_FILE" ]]; then
    DEPLOYED_COMMIT="$(python3 -c "import json; print(json.load(open('$BUILD_FILE')).get('git_commit',''))" 2>/dev/null || echo "")"
    BACKEND_COMMIT="$(python3 -c "import json; print(json.load(open('$BUILD_FILE')).get('backend_commit') or '')" 2>/dev/null || echo "")"
    FRONTEND_COMMIT_BI="$(python3 -c "import json; print(json.load(open('$BUILD_FILE')).get('frontend_commit') or '')" 2>/dev/null || echo "")"
    python3 -m json.tool "$BUILD_FILE" | sed 's/^/  /'
    if [[ -n "$DEPLOYED_COMMIT" ]]; then ok "build-info present ($DEPLOYED_COMMIT)"; else bad "build-info missing git_commit"; fi
  else
    bad "missing $BUILD_FILE"
  fi

  # Backend / tip alignment (mode-aware for frontend_commit handled in served-tree section).
  if [[ "$verify_mode" == "backend" ]]; then
    local be="${BACKEND_COMMIT:-$DEPLOYED_COMMIT}"
    if [[ -n "$be" && "$be" == "$ORIGIN_MAIN" ]]; then
      ok "backend commit == tip ($ORIGIN_MAIN)"
    else
      bad "backend commit ($be) != tip ($ORIGIN_MAIN)"
    fi
  else
    if [[ -n "$DEPLOYED_COMMIT" && "$DEPLOYED_COMMIT" == "$ORIGIN_MAIN" ]]; then
      ok "build-info == origin/main (tip)"
    else
      bad "build-info ($DEPLOYED_COMMIT) != tip ($ORIGIN_MAIN)"
    fi
  fi

  if [[ -f "$project_root/dashboard/dist/index.html" ]]; then
    ok "frontend dist present"
  else
    bad "frontend dist missing"
  fi

  section "2b. Served frontend provenance (Part 3/4)"
  local tip_for_fe="$ORIGIN_MAIN"
  if ! md_verify_frontend_served_tree "$project_root" "$verify_mode" "$tip_for_fe"; then
    : # ok/bad already counted inside helper when using shared ok/bad
  fi
  if [[ -f "$FE_ID" ]]; then
    FE_COMMIT="$(python3 -c "import json; print(json.load(open('$FE_ID')).get('git_commit',''))" 2>/dev/null || echo "")"
    echo "  frontend identity: $FE_COMMIT"
  fi

  section "3. Runtime health + /api/build"
  local API_COMMIT="" API_RELEASE="" ALEMBIC="" API_FE="" API_BE=""
  if curl -sf --max-time 5 "$healthcheck_url" -o "$VR_TMP/health.json" 2>/dev/null; then
    ok "health OK ($healthcheck_url)"
  else
    bad "health unreachable ($healthcheck_url)"
  fi
  if curl -sf --max-time 5 "$build_url" -o "$VR_TMP/build.json" 2>/dev/null; then
    API_COMMIT="$(python3 -c "import json; print(json.load(open('$VR_TMP/build.json')).get('git_commit') or '')" 2>/dev/null || echo "")"
    API_RELEASE="$(python3 -c "import json; print(json.load(open('$VR_TMP/build.json')).get('release') or '')" 2>/dev/null || echo "")"
    ALEMBIC="$(python3 -c "import json; print(json.load(open('$VR_TMP/build.json')).get('alembic_head') or '')" 2>/dev/null || echo "")"
    API_FE="$(python3 -c "import json; print(json.load(open('$VR_TMP/build.json')).get('frontend_commit') or '')" 2>/dev/null || echo "")"
    API_BE="$(python3 -c "import json; print(json.load(open('$VR_TMP/build.json')).get('backend_commit') or '')" 2>/dev/null || echo "")"
    echo "  api release: $API_RELEASE"
    echo "  api commit:  $API_COMMIT"
    echo "  alembic:     $ALEMBIC"
    if [[ "$verify_mode" == "backend" ]]; then
      local expect_be="${BACKEND_COMMIT:-$DEPLOYED_COMMIT}"
      if [[ -n "$API_COMMIT" && "$API_COMMIT" == "$expect_be" ]]; then
        ok "/api/build matches backend tip identity"
      else
        bad "/api/build ($API_COMMIT) != backend tip ($expect_be)"
      fi
      if [[ -n "$API_COMMIT" && "$API_COMMIT" == "$ORIGIN_MAIN" ]]; then
        ok "/api/build matches tip"
      else
        bad "/api/build ($API_COMMIT) != tip ($ORIGIN_MAIN)"
      fi
      if [[ -n "$API_FE" && -n "$FE_COMMIT" && "$API_FE" == "$FE_COMMIT" ]]; then
        ok "/api/build frontend_commit matches preserved FE"
      elif [[ -n "$FRONTEND_COMMIT_BI" && "$API_FE" == "$FRONTEND_COMMIT_BI" ]]; then
        ok "/api/build frontend_commit matches build-info frontend_commit"
      else
        bad "/api/build frontend_commit ($API_FE) inconsistent with preserved FE ($FE_COMMIT)"
      fi
    else
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
    fi
    if [[ -n "$expected_release" ]]; then
      if [[ "$API_RELEASE" == "$expected_release" ]]; then
        ok "/api/build release == tip APP_RELEASE ($expected_release)"
      else
        bad "/api/build release ($API_RELEASE) != tip APP_RELEASE ($expected_release)"
      fi
    fi
    python3 - <<PY 2>/dev/null | sed 's/^/  /' || true
import json
d=json.load(open("$VR_TMP/build.json"))
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
  if curl -sf --max-time 5 "$overview_url" -o "$VR_TMP/overview.json" 2>/dev/null; then
    ok "overview reachable (corpus snapshot best-effort)"
  else
    warn "overview unreachable (auth may be required) — skipped corpus counts"
  fi
  if curl -sf --max-time 3 "http://127.0.0.1:6333/collections" -o "$VR_TMP/qdrant.json" 2>/dev/null; then
    ok "Qdrant reachable"
  else
    warn "Qdrant unreachable on :6333"
  fi

  section "5. Chain summary"
  echo "  mode        : $verify_mode"
  echo "  tip         : $ORIGIN_MAIN"
  echo "  build-info  : $DEPLOYED_COMMIT"
  echo "  backend     : ${BACKEND_COMMIT:-$DEPLOYED_COMMIT}"
  echo "  frontend_bi : ${FRONTEND_COMMIT_BI:-missing}"
  echo "  frontend    : ${FE_COMMIT:-missing}"
  echo "  /api/build  : ${API_COMMIT:-unreachable}"
  if [[ "$verify_mode" == "backend" ]]; then
    if [[ -n "$ORIGIN_MAIN" && "$ORIGIN_MAIN" == "${API_COMMIT:-}" && "$ORIGIN_MAIN" == "${BACKEND_COMMIT:-$DEPLOYED_COMMIT}" && -n "$FE_COMMIT" && "$FE_COMMIT" == "${FRONTEND_COMMIT_BI:-}" ]]; then
      ok "BACKEND CHAIN OK (tip == backend == /api/build; FE self-consistent, may lag tip)"
    else
      bad "BACKEND CHAIN BROKEN — tip/backend/api or FE self-consistency failed"
    fi
  else
    if [[ -n "$ORIGIN_MAIN" && "$ORIGIN_MAIN" == "$DEPLOYED_COMMIT" && "$DEPLOYED_COMMIT" == "${API_COMMIT:-}" && "$DEPLOYED_COMMIT" == "${FE_COMMIT:-}" ]]; then
      ok "FULL CHAIN ALIGNED (tip == build-info == frontend == /api/build)"
    else
      bad "CHAIN BROKEN — commits do not all match"
    fi
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
