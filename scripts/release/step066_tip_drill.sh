#!/usr/bin/env bash
# RFC-100 Step 066 — code tip rollback drill (One Command only; no force-push; no DB/Qdrant restore).
#
# Places known-good tip tree (148138e) on origin/main via revert (no force-push), deploys,
# then restores current tip tree (a41198f) the same way.
#
# Requires: clean git tree, network push credentials, sudo for deploy.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ROLLBACK_TIP="${STEP066_ROLLBACK_TIP:-148138eb1f27c85a23c0ddfb47f0ad812d90a36e}"
RESTORE_TIP="${STEP066_RESTORE_TIP:-a41198f28f59c2d22c78e63f0afec9448ca8fe0c}"
OUT="$ROOT/docs/releases/1.0-step-066-rollback-report.json"
BASE="${STAGING_BASE_URL:-http://127.0.0.1:8000}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "FAIL: working tree must be clean for tip drill (stash Step 066 untracked files first)"
  exit 1
fi

git fetch origin
pre_build="$(curl -sfS --max-time 30 "$BASE/api/build" || echo '{}')"
pre_head="$(git rev-parse HEAD)"
pre_origin="$(git rev-parse origin/main)"
pre_tree="$(git rev-parse "${RESTORE_TIP}^{tree}")"
rollback_tree="$(git rev-parse "${ROLLBACK_TIP}^{tree}")"

echo "==> Pre-drill: HEAD=$pre_head origin/main=$pre_origin"

if [[ "$(git rev-parse HEAD)" != "$RESTORE_TIP" ]] && [[ "$(git rev-parse HEAD^{tree})" != "$pre_tree" ]]; then
  echo "FAIL: HEAD must be restore tip $RESTORE_TIP (or same tree) before drill (got $(git rev-parse HEAD))"
  exit 1
fi

# Prefer exact SHA match for initial revert of Step 065 commit
if [[ "$(git rev-parse HEAD)" == "$RESTORE_TIP" ]]; then
  echo "==> Revert $RESTORE_TIP → tree of $ROLLBACK_TIP"
  git revert --no-edit "$RESTORE_TIP"
else
  echo "FAIL: exact restore tip required for deterministic revert (HEAD=$(git rev-parse HEAD))"
  exit 1
fi

git push origin main
sudo bash "$ROOT/deploy/manage_deploy.sh" deploy full
mid_build="$(curl -sfS --max-time 30 "$BASE/api/build")"
mid_head="$(git rev-parse HEAD)"
mid_tree="$(git rev-parse HEAD^{tree})"
bash "$ROOT/deploy/manage_deploy.sh" verify-release
bash "$ROOT/deploy/manage_deploy.sh" smoke || true

if [[ "$mid_tree" != "$rollback_tree" ]]; then
  echo "FAIL: mid tree $mid_tree != rollback tree $rollback_tree"
  exit 1
fi

echo "==> Restore current tip tree by reverting the revert"
git revert --no-edit HEAD
git push origin main
sudo bash "$ROOT/deploy/manage_deploy.sh" deploy full
post_build="$(curl -sfS --max-time 30 "$BASE/api/build")"
post_head="$(git rev-parse HEAD)"
post_tree="$(git rev-parse HEAD^{tree})"
bash "$ROOT/deploy/manage_deploy.sh" verify-release
bash "$ROOT/deploy/manage_deploy.sh" smoke || true

python3 - <<PY
import json
from datetime import datetime, timezone
pre=json.loads('''${pre_build}''')
mid=json.loads('''${mid_build}''')
post=json.loads('''${post_build}''')
restore_tree="$pre_tree"
rollback_tree="$rollback_tree"
mid_tree="$mid_tree"
post_tree="$post_tree"
verdict="PASS"
if mid_tree != rollback_tree:
    verdict="FAIL"
if post_tree != restore_tree:
    verdict="FAIL"
report={
  "step":"066",
  "drill":"code_tip_rollback",
  "finished_at": datetime.now(timezone.utc).isoformat(),
  "rollback_tip_requested": "$ROLLBACK_TIP",
  "restore_tip_requested": "$RESTORE_TIP",
  "pre_head": "$pre_head",
  "pre_origin": "$pre_origin",
  "mid_head": "$mid_head",
  "post_head": "$post_head",
  "rollback_tree": rollback_tree,
  "restore_tree": restore_tree,
  "mid_tree": mid_tree,
  "post_tree": post_tree,
  "pre_build": pre,
  "mid_build_commit": str(mid.get("git_commit") or ""),
  "post_build_commit": str(post.get("git_commit") or ""),
  "method": "git revert (no force-push) + sudo deploy full twice; identity by tree SHA",
  "db_restore": False,
  "qdrant_restore": False,
  "force_push": False,
  "verdict": verdict,
}
open("$OUT","w",encoding="utf-8").write(json.dumps(report,indent=2)+"\n")
print(json.dumps({"verdict": verdict, "mid_head": "$mid_head", "post_head": "$post_head"}, indent=2))
raise SystemExit(0 if verdict=="PASS" else 1)
PY
