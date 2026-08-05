#!/usr/bin/env bash
# One Command Deployment — Definition of Tested (Engineering Package).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export ROOT
DS="$ROOT/deploy/lib/deploy_source.sh"
MD_DEC="$ROOT/deploy/lib/migration_decision.sh"
VR="$ROOT/deploy/lib/verify_release.sh"
VR_CLI="$ROOT/scripts/release/verify-release.sh"
MAN="$ROOT/deploy/lib/manifest.sh"
CLI="$ROOT/deploy/lib/cli.sh"
MD="$ROOT/deploy/manage_deploy.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "OK: $*"; }

# --- Pipeline order + fail-hard restart ---
python3 - <<'PY' || exit 1
from pathlib import Path
import os, re, sys
text = Path(os.environ["ROOT"], "deploy/lib/deploy_source.sh").read_text(encoding="utf-8")
# Order must hold inside md_deploy_from_main (not helper definitions above it).
body = text.split("md_deploy_from_main()", 1)[1]
stages = [
    r"\[deploy 1/13\] PREFLIGHT",
    r"md_deploy_mandatory_backup",
    r"\[deploy 3/13\] MIGRATION DECISION",
    r"\[deploy 4/13\] SCHEMA-FIRST",
    r"\[deploy 5/13\] BUILD",
    r"\[deploy 6/13\] SYNC",
    r"\[deploy 7/13\] POST-SYNC MIGRATE",
    r"md_deploy_restart_hard",
    r"md_deploy_health_hard",
    r"\[deploy 10/13\] VERIFY RELEASE",
    r"\[deploy 11/13\] SMOKE",
    r"\[deploy 12/13\] WRITE FINAL REPORT",
    r"\[deploy 13/13\] SUCCESS",
]
pos = 0
for s in stages:
    m = re.search(s, body)
    if not m:
        print(f"FAIL: missing stage in md_deploy_from_main: {s}", file=sys.stderr)
        sys.exit(1)
    if m.start() < pos:
        print(f"FAIL: stage out of order: {s}", file=sys.stderr)
        sys.exit(1)
    pos = m.start()

fn = text.split("md_deploy_restart_hard()", 1)[1].split("md_deploy_health_hard()", 1)[0]
if "|| true" in fn:
    print("FAIL: restart helper still soft-fails with || true", file=sys.stderr)
    sys.exit(1)
if re.search(r"restart --module backend[\s\S]{0,200}\|\|\s*true", text):
    print("FAIL: soft-fail restart still present in deploy_source", file=sys.stderr)
    sys.exit(1)

if "md_deploy_fail health" not in text:
    print("FAIL: health must call md_deploy_fail", file=sys.stderr); sys.exit(1)
if "md_deploy_fail verify_release" not in text:
    print("FAIL: verify must call md_deploy_fail", file=sys.stderr); sys.exit(1)
if "md_deploy_fail smoke" not in text:
    print("FAIL: smoke must call md_deploy_fail", file=sys.stderr); sys.exit(1)
if "md_deploy_fail report" not in text:
    print("FAIL: report write failure must be fatal", file=sys.stderr); sys.exit(1)

if "migrate release --yes" not in text:
    print("FAIL: schema-first must call migrate release --yes", file=sys.stderr); sys.exit(1)
# Schema-first must reach the CLI subcommand path. MD_SKIP_CLI=1 on that
# invocation sends "migrate" through legacy parse_args → "Unknown option: migrate".
import re as _re

sf_section_m = _re.search(
    r"# --- 4/13 CONDITIONAL SCHEMA-FIRST ---.*?\# --- 5/13 BUILD ---",
    text,
    _re.S,
)
sf_section = sf_section_m.group(0) if sf_section_m else ""
if not sf_section:
    print("FAIL: cannot locate schema-first section", file=sys.stderr)
    sys.exit(1)
if "migrate release --yes" not in sf_section:
    print("FAIL: schema-first section missing migrate release --yes", file=sys.stderr)
    sys.exit(1)
# Invocation line(s) only — ignore comments that document the MD_SKIP_CLI=1 failure mode.
inv_lines = [
    ln for ln in sf_section.splitlines()
    if "migrate release --yes" in ln and not ln.lstrip().startswith("#")
]
# Also capture the preceding "if !" line that sets MD_SKIP_CLI.
inv_ctx = []
lines = sf_section.splitlines()
for i, ln in enumerate(lines):
    if "migrate release --yes" in ln and not ln.lstrip().startswith("#"):
        inv_ctx.extend(lines[max(0, i - 2) : i + 1])
inv_blob = "\n".join(inv_ctx)
if "MD_SKIP_CLI=1" in inv_blob:
    print(
        "FAIL: schema-first must not set MD_SKIP_CLI=1 when calling migrate release",
        file=sys.stderr,
    )
    sys.exit(1)
if "MD_SKIP_CLI=0" not in inv_blob:
    print(
        "FAIL: schema-first must set MD_SKIP_CLI=0 so migrate release uses the CLI path",
        file=sys.stderr,
    )
    sys.exit(1)
if "ignoring configured value" not in text:
    print("FAIL: must warn/ignore stale RELEASE_VERSION", file=sys.stderr); sys.exit(1)
if "deploy_guard_read_app_release" not in text:
    print("FAIL: must read tip APP_RELEASE", file=sys.stderr); sys.exit(1)
if "MD_REPORT_MIGRATION_POST_SYNC" not in text:
    print("FAIL: post-sync result must be reported", file=sys.stderr); sys.exit(1)

# Sync vs post-sync migrate must be separately fail-classified (Evidence Review fix).
if "md_deploy_fail sync" not in text:
    print("FAIL: missing md_deploy_fail sync", file=sys.stderr); sys.exit(1)
if "md_deploy_fail post_sync_migrate" not in text:
    print("FAIL: missing md_deploy_fail post_sync_migrate", file=sys.stderr); sys.exit(1)
if "MD_SKIP_RUN_MIGRATIONS=1" not in text:
    print("FAIL: sync stage must set MD_SKIP_RUN_MIGRATIONS=1", file=sys.stderr); sys.exit(1)
# Order inside md_deploy_from_main: sync fail path, then post_sync_migrate fail, then restart
i_sync = body.find("md_deploy_fail sync")
i_psm = body.find("md_deploy_fail post_sync_migrate")
i_restart = body.find("md_deploy_restart_hard")
if not (0 <= i_sync < i_psm < i_restart):
    print(
        f"FAIL: expected sync fail < post_sync_migrate fail < restart "
        f"(got {i_sync}, {i_psm}, {i_restart})",
        file=sys.stderr,
    )
    sys.exit(1)
# Combined conflation must be gone
if "sync or post-sync migrate failed" in text:
    print("FAIL: combined sync/post-sync failure attribution still present", file=sys.stderr)
    sys.exit(1)

print("OK: pipeline order + fail-hard + identity + schema-first wiring")
PY

# --- Shared verify core ---
[[ -f "$VR" ]] || fail "missing deploy/lib/verify_release.sh"
[[ -f "$VR_CLI" ]] || fail "missing scripts/release/verify-release.sh"
grep -q 'md_verify_release_run' "$VR" || fail "shared core missing md_verify_release_run"
grep -q 'source .*verify_release.sh' "$VR_CLI" || fail "CLI must source shared verify core"
grep -q 'md_verify_release_run' "$VR_CLI" || fail "CLI must call md_verify_release_run"
# No duplicated FULL CHAIN logic in CLI
if grep -q 'FULL CHAIN ALIGNED' "$VR_CLI"; then
  fail "CLI must not duplicate verification logic"
fi
grep -q 'md_verify_release_run' "$DS" || fail "deploy full must call shared verify core"
pass "verify-release shared core (deploy + CLI)"

# --- Phase 2 contracts (T19/T20/T22/T24) ---
grep -q 'md_verify_frontend_served_tree' "$VR" || fail "Phase2: missing md_verify_frontend_served_tree"
grep -q 'mktemp -d /tmp/ai-site-agent-vr-' "$VR" || fail "Phase2: verify must use writable mktemp workspace"
if grep -E '/tmp/vr-(health|build|overview|qdrant)\.json' "$VR"; then
  fail "Phase2: fixed /tmp/vr-*.json must be removed"
fi
grep -q 'md_preserve_backend_frontend_identity' "$DS" || fail "Phase2: missing backend FE preserve helper"
grep -q 'md_publish_frontend_artifact' "$DS" || fail "Phase2: Phase1 publish helper must remain"
grep -q 'dist.next' "$DS" || fail "Phase2: dist.next publication must remain"
# verify mode passed from deploy
grep -q 'md_verify_release_run.*"\$mode"\|md_verify_release_run .*\$mode' "$DS" \
  || grep -q 'md_verify_release_run "$repo" "$MD_DEPLOY_PROJECT_ROOT" "$commit" "$MD_DEPLOY_RELEASE" "$mode"' "$DS" \
  || fail "Phase2: deploy must pass mode into md_verify_release_run"
python3 - <<'PY' || exit 1
from pathlib import Path
import os, sys
body = Path(os.environ["ROOT"], "deploy/lib/deploy_source.sh").read_text().split("md_deploy_from_main()",1)[1]
i_v = body.find("md_deploy_fail verify_release")
i_s = body.find("md_deploy_fail smoke")
if not (0 <= i_v < i_s):
    print("FAIL: verify_release fail must precede smoke fail", file=sys.stderr)
    sys.exit(1)
print("OK: verify/smoke gate order")
PY
pass "Phase 2 verify/smoke/temps/backend-preserve/publication freeze contracts"

# --- Migration decision outcomes ---
[[ -f "$MD_DEC" ]] || fail "missing migration_decision.sh"
grep -q 'schema_first' "$MD_DEC" || fail "decision must emit schema_first"
grep -q 'post_sync_only' "$MD_DEC" || fail "decision must emit post_sync_only"
grep -q 'database unreachable' "$MD_DEC" || fail "decision must fail on DB unreachable"
grep -q 'live DB revision' "$MD_DEC" || fail "decision must fail when live ahead/unknown"
grep -q 'multiple alembic heads' "$MD_DEC" || fail "decision must fail on multiple heads"
pass "migration decision vocabulary"

# Fixture: file-list helpers (no live DB)
# shellcheck source=deploy/lib/migration_decision.sh
source "$MD_DEC"
TMP="$(mktemp -d /tmp/ocd-migdec-XXXXXX)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT
mkdir -p "$TMP/tip" "$TMP/opt"
echo 'x' >"$TMP/tip/0001_a.py"
echo 'x' >"$TMP/tip/0002_b.py"
echo 'x' >"$TMP/opt/0001_a.py"
# tip has extra file → would be schema_first if compared
tip_files="$(printf '%s\n' '0001_a.py' '0002_b.py')"
missing=0
while IFS= read -r f; do
  [[ -f "$TMP/opt/$f" ]] || missing=1
done <<< "$tip_files"
[[ "$missing" -eq 1 ]] || fail "fixture: missing tip file should be detected"
echo 'x' >"$TMP/opt/0002_b.py"
missing=0
while IFS= read -r f; do
  [[ -f "$TMP/opt/$f" ]] || missing=1
done <<< "$tip_files"
[[ "$missing" -eq 0 ]] || fail "fixture: complete /opt should be post_sync_only"
pass "schema-first vs post_sync_only file compare fixture"

# --- Report schema + rollback recommendations ---
# shellcheck source=deploy/lib/manifest.sh
source "$MAN"
[[ "$(md_rollback_recommendation preflight failed)" == "none_pre_sync" ]] || fail "rollback preflight"
[[ "$(md_rollback_recommendation backup failed)" == "none_pre_sync" ]] || fail "rollback backup"
[[ "$(md_rollback_recommendation migration_decision failed)" == "none_pre_sync" ]] || fail "rollback migdec"
[[ "$(md_rollback_recommendation build failed)" == "none_pre_sync" ]] || fail "rollback build"
[[ "$(md_rollback_recommendation schema_first failed)" == "review_schema_no_autodowngrade" ]] || fail "rollback SF"
[[ "$(md_rollback_recommendation sync failed)" == "redeploy_known_good_tip" ]] || fail "rollback sync"
[[ "$(md_rollback_recommendation post_sync_migrate failed)" == "redeploy_known_good_tip" ]] || fail "rollback post_sync_migrate"
[[ "$(md_rollback_recommendation restart failed)" == "redeploy_known_good_tip" ]] || fail "rollback restart"
[[ "$(md_rollback_recommendation '' success)" == "none" ]] || fail "rollback success"
pass "rollback recommendation vocabulary"

# Report failed_stage distinguishes sync vs post_sync_migrate
REPORT_ROOT="$TMP/opt_proj"
mkdir -p "$REPORT_ROOT/deployments" "$REPORT_ROOT/backups"
echo "fake" >"$REPORT_ROOT/backups/test.dump"

write_failed_stage_report() {
  local stage="$1"
  MD_REPORT_OUTCOME="failed"
  MD_REPORT_DEPLOYED_COMMIT="abc123def456"
  MD_REPORT_DEPLOYED_COMMIT_SHORT="abc123d"
  MD_REPORT_DEPLOYED_RELEASE="0.9"
  MD_REPORT_PREVIOUS_COMMIT="prevprev"
  MD_REPORT_PREVIOUS_RELEASE="0.8"
  MD_REPORT_ORIGIN_MAIN_COMMIT="abc123def456"
  MD_REPORT_BACKUP_PATH="$REPORT_ROOT/backups/test.dump"
  MD_REPORT_BACKUP_ID="test"
  MD_REPORT_MIGRATION_DECISION="post_sync_only"
  MD_REPORT_MIGRATION_SCHEMA_FIRST="skipped"
  MD_REPORT_PARTIAL_DEPLOY="true"
  MD_REPORT_FAILED_STAGE="$stage"
  MD_REPORT_FAILED_STAGE_DETAIL="fixture $stage"
  MD_REPORT_DURATION_SECONDS="3"
  if [[ "$stage" == "sync" ]]; then
    MD_REPORT_MIGRATION_POST_SYNC="not_reached"
  else
    MD_REPORT_MIGRATION_POST_SYNC="failed"
  fi
  MD_REPORT_RESTART_RESULT="not_reached"
  MD_REPORT_HEALTH_RESULT="not_reached"
  MD_REPORT_VERIFY_RESULT="not_reached"
  MD_REPORT_SMOKE_RESULT="not_reached"
  md_write_deploy_report "$REPORT_ROOT" || fail "report write for $stage"
  python3 - "$MD_REPORT_MANIFEST_PATH" "$stage" <<'PY' || exit 1
import json, sys
d = json.load(open(sys.argv[1]))
stage = sys.argv[2]
assert d["outcome"] == "failed"
assert d["failed_stage"] == stage, d["failed_stage"]
assert d["partial_deploy"] == "true"
assert d["rollback_recommendation"] == "redeploy_known_good_tip"
print(f"OK: report failed_stage={stage}")
PY
}
write_failed_stage_report sync
write_failed_stage_report post_sync_migrate
pass "Deployment Report sync vs post_sync_migrate failed_stage"

# manage_deploy honors skip for separate post-sync stage
grep -q 'MD_SKIP_RUN_MIGRATIONS' "$ROOT/deploy/manage_deploy.sh" \
  || fail "manage_deploy must honor MD_SKIP_RUN_MIGRATIONS"
pass "manage_deploy MD_SKIP_RUN_MIGRATIONS gate"

MD_REPORT_OUTCOME="success"
MD_REPORT_DEPLOYED_COMMIT="abc123def456"
MD_REPORT_DEPLOYED_COMMIT_SHORT="abc123d"
MD_REPORT_DEPLOYED_RELEASE="0.9"
MD_REPORT_PREVIOUS_COMMIT="prevprev"
MD_REPORT_PREVIOUS_RELEASE="0.8"
MD_REPORT_ORIGIN_MAIN_COMMIT="abc123def456"
MD_REPORT_BACKUP_PATH="$REPORT_ROOT/backups/test.dump"
MD_REPORT_BACKUP_ID="test"
MD_REPORT_MIGRATION_DECISION="post_sync_only"
MD_REPORT_MIGRATION_SCHEMA_FIRST="skipped"
MD_REPORT_MIGRATION_POST_SYNC="ok"
MD_REPORT_RESTART_RESULT="ok"
MD_REPORT_HEALTH_RESULT="ok"
MD_REPORT_VERIFY_RESULT="pass"
MD_REPORT_SMOKE_RESULT="pass"
MD_REPORT_PARTIAL_DEPLOY="false"
MD_REPORT_FAILED_STAGE=""
MD_REPORT_FAILED_STAGE_DETAIL=""
MD_REPORT_DURATION_SECONDS="12"
md_write_deploy_report "$REPORT_ROOT" || fail "success report write"
[[ -n "${MD_REPORT_MANIFEST_PATH:-}" && -f "$MD_REPORT_MANIFEST_PATH" ]] || fail "manifest path missing"
python3 - "$MD_REPORT_MANIFEST_PATH" <<'PY' || exit 1
import json, sys
req = [
  "outcome","deployed_commit","deployed_commit_short","deployed_release",
  "previous_commit","previous_release","origin_main_commit","project_root",
  "backup_id","backup_path","migration_decision","migration_schema_first",
  "migration_post_sync","alembic_head","restart_result","health_result",
  "verify_release_result","smoke_result","partial_deploy","failed_stage",
  "failed_stage_detail","rollback_recommendation","duration_seconds",
  "operator","manifest_time","manifest_path",
]
d = json.load(open(sys.argv[1]))
missing = [k for k in req if k not in d]
if missing:
    print("FAIL: missing fields", missing, file=sys.stderr); sys.exit(1)
assert d["outcome"] == "success"
assert d["partial_deploy"] == "false"
assert d["rollback_recommendation"] == "none"
assert d["smoke_result"] == "pass"
# No secrets
blob = json.dumps(d)
for bad in ("password", "postgresql+psycopg://", "://ai_agent:", "SECRET", "Bearer "):
    if bad.lower() in blob.lower() and "password" in bad.lower():
        pass
if "s3cret" in blob or "postgresql+psycopg://" in blob:
    print("FAIL: secret-like URL in report", file=sys.stderr); sys.exit(1)
print("OK: success report mandatory fields")
PY
[[ -L "$REPORT_ROOT/deployments/latest.json" || -f "$REPORT_ROOT/deployments/latest.json" ]] \
  || fail "latest.json missing after success"

# Failed report + latest.json update
MD_REPORT_OUTCOME="failed"
MD_REPORT_FAILED_STAGE="restart"
MD_REPORT_FAILED_STAGE_DETAIL="backend restart failed"
MD_REPORT_PARTIAL_DEPLOY="true"
MD_REPORT_RESTART_RESULT="fail"
MD_REPORT_HEALTH_RESULT="not_reached"
MD_REPORT_VERIFY_RESULT="not_reached"
MD_REPORT_SMOKE_RESULT="not_reached"
MD_REPORT_DURATION_SECONDS="5"
md_write_deploy_report "$REPORT_ROOT" || fail "failed report write"
python3 - "$MD_REPORT_MANIFEST_PATH" "$REPORT_ROOT/deployments" <<'PY' || exit 1
import json, sys, os
from pathlib import Path
d = json.load(open(sys.argv[1]))
assert d["outcome"] == "failed"
assert d["failed_stage"] == "restart"
assert d["partial_deploy"] == "true"
assert d["rollback_recommendation"] == "redeploy_known_good_tip"
assert "manifest_time" in d and "T" in d["manifest_time"]
# latest points at newest
deploy = Path(sys.argv[2])
latest = deploy / "latest.json"
assert latest.exists()
# resolve symlink or pointer
target = latest.resolve() if latest.is_symlink() else latest
# If symlink, target should be the failed report basename
if latest.is_symlink():
    assert latest.resolve().name == Path(sys.argv[1]).name
print("OK: failed report + latest.json")
PY
pass "deployment report SUCCESS/FAILED schema"

# Stdout contract present in deploy_source
grep -q 'VERDICT: SUCCESS' "$DS" || fail "missing SUCCESS stdout"
grep -q 'VERDICT: FAILED' "$DS" || fail "missing FAILED stdout"
grep -q 'manifest_unavailable' "$DS" || fail "missing manifest_unavailable"
pass "stdout SUCCESS/FAILED contract"

# --- CLI / docs: one canonical command ---
help_out="$(bash "$MD" help 2>&1 || true)"
echo "$help_out" | grep -q 'sudo bash deploy/manage_deploy.sh deploy full' \
  || echo "$help_out" | grep -qi 'ONE command' \
  || fail "help must present one-command normal release"
echo "$help_out" | grep -qi 'diagnostics\|recovery\|NOT required' \
  || fail "help must classify standalone as diagnostics/recovery"
# Must NOT document multi-command normal cutover as required
if echo "$help_out" | grep -q 'backup db → migrate release → deploy full'; then
  fail "help must not require multi-command schema-first cutover"
fi
pass "CLI help one-command contract"

python3 - <<'PY' || exit 1
from pathlib import Path
import os, re, sys
root = Path(os.environ["ROOT"])
active = [
    root / "docs/RELEASE_ENGINEERING_WORKFLOW.md",
    root / "docs/releases/RELEASE-CHECKLIST.md",
    root / "docs/releases/RELEASE-ENGINEERING-HARDENING.md",
    root / "docs/DEPLOYMENT.md",
]
# Forbidden: required multi-command normal-release choreography in active docs
bad = re.compile(
    r"status\s*→\s*backup db\s*→\s*migrate release\s*→\s*verify schema head\s*→\s*deploy full",
    re.I,
)
for d in active:
    text = d.read_text(encoding="utf-8")
    if bad.search(text):
        print(f"FAIL: active doc still has multi-command cutover: {d}", file=sys.stderr)
        sys.exit(1)
    if "sudo bash deploy/manage_deploy.sh deploy full" not in text \
       and "manage_deploy.sh deploy full" not in text:
        print(f"FAIL: active doc missing deploy full: {d}", file=sys.stderr)
        sys.exit(1)
print("OK: active docs one-command")
PY

# Historical reports may retain old sequences — do not fail on them.
pass "docs contract (active only)"

# --- Regression: recovery migrate release still present ---
echo "$help_out" | grep -q 'migrate release' || fail "help must retain migrate release recovery"
grep -q 'md_migrate_release' "$CLI" || fail "CLI must retain migrate release"
pass "recovery migrate release retained"

# --- migrate-machine still reuses deploy full (no new multi-command operator path) ---
MM="$ROOT/deploy/lib/migrate_machine.sh"
grep -q 'md_mm_run_cli deploy full' "$MM" || fail "migrate-machine must reuse deploy full"
pass "migrate-machine reuses deploy full"

echo "OK: One Command Deployment Definition of Tested passed"
