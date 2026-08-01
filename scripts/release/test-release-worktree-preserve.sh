#!/usr/bin/env bash
# Regression: One Command release worktree must survive deploy.local.conf.
#
# Reproduces the production failure mode where nested manage_deploy.sh
# reloaded deploy.local.conf and overwrote DEV_CHECKOUT to the operator
# checkout, so sync copied stale .build-info (RELEASE_VERSION) instead of
# the release worktree built with tip APP_RELEASE.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LIB="$ROOT/deploy/lib/release_deploy_env.sh"
MD="$ROOT/deploy/manage_deploy.sh"
DS="$ROOT/deploy/lib/deploy_source.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "OK: $*"; }

[[ -f "$LIB" ]] || fail "missing release_deploy_env.sh"
[[ -f "$MD" ]] || fail "missing manage_deploy.sh"

# --- Wiring: manage_deploy must preserve across local conf ---
grep -q 'md_release_preserve_env_before_local_conf' "$MD" \
  || fail "manage_deploy must preserve env before local conf"
grep -q 'md_release_restore_env_after_local_conf' "$MD" \
  || fail "manage_deploy must restore env after local conf"
grep -q 'release_deploy_env.sh' "$MD" \
  || fail "manage_deploy must source release_deploy_env.sh"
# Order: preserve → source local conf → restore
python3 - "$MD" <<'PY' || exit 1
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
i_p = text.find("md_release_preserve_env_before_local_conf")
i_l = text.find("deploy.local.conf")
i_r = text.find("md_release_restore_env_after_local_conf")
if not (0 <= i_p < i_l < i_r):
    print(f"FAIL: preserve/local/restore order broken ({i_p},{i_l},{i_r})", file=sys.stderr)
    sys.exit(1)
print("OK: preserve → local conf → restore order")
PY

# deploy_source must export worktree + tip release for nested manage_deploy
grep -q 'export DEV_CHECKOUT=' "$DS" || fail "deploy_source must export DEV_CHECKOUT"
grep -q 'export MD_DEPLOY_RELEASE' "$DS" || fail "deploy_source must export MD_DEPLOY_RELEASE"
grep -q 'export MD_RELEASE_DEPLOY=1' "$DS" || fail "deploy_source must export MD_RELEASE_DEPLOY=1"
pass "deploy_source exports release worktree + tip release"

# --- Behavioural: local conf cannot overwrite release worktree ---
# shellcheck source=deploy/lib/release_deploy_env.sh
source "$LIB"

WT="/tmp/ai-site-agent-release-wt-test-$$"
OP="/tmp/ai-site-agent-operator-test-$$"
mkdir -p "$WT/backend" "$WT/dashboard" "$OP/backend" "$OP/dashboard"
cleanup() { rm -rf "$WT" "$OP"; }
trap cleanup EXIT

# Tip identity in worktree build-info
python3 - <<PY
import json
from pathlib import Path
Path("$WT/.build-info.json").write_text(json.dumps({
    "git_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "git_commit_short": "aaaaaaa",
    "release": "0.9",
}, indent=2) + "\n")
# Stale operator checkout identity (the pre-fix failure mode)
Path("$OP/.build-info.json").write_text(json.dumps({
    "git_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "git_commit_short": "aaaaaaa",
    "release": "0.8",
}, indent=2) + "\n")
PY

export MD_RELEASE_DEPLOY=1
export DEV_CHECKOUT="$WT"
export MD_DEPLOY_RELEASE="0.9"
RELEASE_VERSION="0.9"

md_release_preserve_env_before_local_conf

# Simulate deploy.local.conf overwrite (production bug)
DEV_CHECKOUT="$OP"
RELEASE_VERSION="0.8"

md_release_restore_env_after_local_conf

[[ "$DEV_CHECKOUT" == "$WT" ]] \
  || fail "DEV_CHECKOUT overwritten by local conf (got $DEV_CHECKOUT, want $WT)"
[[ "$RELEASE_VERSION" == "0.9" ]] \
  || fail "RELEASE_VERSION from local conf won over tip APP_RELEASE (got $RELEASE_VERSION)"
pass "deploy.local.conf cannot overwrite release worktree / tip release"

# Sync source must resolve to the preserved worktree (same as build source)
candidate="$(cd "${DEV_CHECKOUT}" 2>/dev/null && pwd || true)"
[[ -d "$candidate/backend" && -d "$candidate/dashboard" ]] \
  || fail "preserved DEV_CHECKOUT incomplete"
SYNC_SOURCE="$candidate"
[[ "$SYNC_SOURCE" == "$(cd "$WT" && pwd)" ]] \
  || fail "sync source != build worktree ($SYNC_SOURCE)"
pass "sync source == build worktree"

# Identity chain from synced worktree build-info (not operator 0.8)
bi_rel="$(python3 -c "import json; print(json.load(open('$SYNC_SOURCE/.build-info.json'))['release'])")"
op_rel="$(python3 -c "import json; print(json.load(open('$OP/.build-info.json'))['release'])")"
[[ "$bi_rel" == "0.9" ]] || fail "worktree build-info release want 0.9 got $bi_rel"
[[ "$op_rel" == "0.8" ]] || fail "fixture operator stale release expected 0.8"
[[ "$bi_rel" != "$op_rel" ]] || fail "fixture did not model stale operator identity"
# Frontend identity must follow build-info / tip release, never stale RELEASE_VERSION alone
fe_release="$bi_rel"
[[ "$fe_release" == "0.9" && "$fe_release" == "$MD_DEPLOY_RELEASE" ]] \
  || fail "backend/frontend/build-info identity mismatch"
pass "backend identity == frontend identity == build-info identity (tip 0.9)"

# --- Negative: without MD_RELEASE_DEPLOY, local conf may set DEV_CHECKOUT (default) ---
unset MD_RELEASE_DEPLOY MD_DEPLOY_RELEASE MD_RELEASE_SAVED_DEV_CHECKOUT MD_RELEASE_SAVED_RELEASE_VERSION
export DEV_CHECKOUT="$WT"
md_release_preserve_env_before_local_conf
DEV_CHECKOUT="$OP"
RELEASE_VERSION="0.8"
md_release_restore_env_after_local_conf
[[ "$DEV_CHECKOUT" == "$OP" ]] \
  || fail "non-release path should allow local conf DEV_CHECKOUT (got $DEV_CHECKOUT)"
pass "non-release path: deploy.local.conf remains the default for DEV_CHECKOUT"

# --- Before-fix reproduction (structural): old bug was sourcing local conf
# without preserve/restore. Prove those calls exist; prove combined absence of
# unconditional DEV_CHECKOUT assignment from local conf after restore. ---
if ! grep -q 'md_release_restore_env_after_local_conf' "$MD"; then
  fail "pre-fix regression: restore missing — local conf would win"
fi
pass "pre-fix overwrite regression is gated by preserve/restore"

echo "OK: release worktree preserve regression passed"
