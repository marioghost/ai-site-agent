#!/usr/bin/env bash
# Regression: One Command + schema-first recovery docs stay aligned.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MD="$ROOT/deploy/manage_deploy.sh"
export ROOT
fail() { echo "FAIL: $*" >&2; exit 1; }

# --- 1. Help: one-command normal release; migrate variants for recovery ---
help_out="$(bash "$MD" help 2>&1 || true)"
echo "$help_out" | grep -qE '^[[:space:]]*migrate[[:space:]]' \
  || fail "help missing bare migrate"
echo "$help_out" | grep -q 'migrate live' || fail "help missing migrate live"
echo "$help_out" | grep -q 'migrate release' || fail "help missing migrate release"
echo "$help_out" | grep -qi 'alias of bare migrate' \
  || fail "help must say migrate live is alias of bare migrate"
echo "$help_out" | grep -qi 'live /opt' || fail "help must say bare migrate uses /opt tree"
echo "$help_out" | grep -qi 'origin/main' || fail "help must mention origin/main for migrate release"
echo "$help_out" | grep -qiE 'post-sync|idempotent' \
  || fail "help must document post-sync Alembic"
echo "$help_out" | grep -qiE 'ONE command|Normal release' \
  || fail "help must present one-command normal release"
echo "$help_out" | grep -qiE 'recovery|diagnostics' \
  || fail "help must classify migrate release / verify as recovery/diagnostics"
if echo "$help_out" | grep -q 'backup db → migrate release → deploy full'; then
  fail "help must not require multi-command cutover for normal release"
fi
echo "OK: help one-command + migrate recovery"

# --- Required docs exist ---
DOCS=(
  "$ROOT/docs/releases/RELEASE-CHECKLIST.md"
  "$ROOT/docs/operations/RELEASE-0.8-PRE-DEPLOY-PLAN.md"
  "$ROOT/docs/releases/0.8-step-057-release-closure.md"
  "$ROOT/docs/releases/RELEASE-0.8-ACCEPTANCE-REPORT.md"
  "$ROOT/docs/operations/POST-0.8-MACHINE-MIGRATION.md"
  "$ROOT/docs/RELEASE_ENGINEERING_WORKFLOW.md"
  "$ROOT/docs/DEPLOYMENT.md"
)
for doc in "${DOCS[@]}"; do
  [[ -f "$doc" ]] || fail "missing doc: $doc"
done

# --- 2. Active operator docs: one canonical deploy command ---
for doc in \
  "$ROOT/docs/releases/RELEASE-CHECKLIST.md" \
  "$ROOT/docs/RELEASE_ENGINEERING_WORKFLOW.md" \
  "$ROOT/docs/DEPLOYMENT.md" \
  "$ROOT/docs/operations/POST-0.8-MACHINE-MIGRATION.md"
do
  grep -q 'deploy full' "$doc" || fail "$doc missing deploy full"
  # Must not require the old multi-command normal-release sequence
  if grep -qiE 'status[[:space:]]*→[[:space:]]*backup db[[:space:]]*→[[:space:]]*migrate release' "$doc"; then
    fail "$doc still documents multi-command normal cutover"
  fi
done
echo "OK: active docs use one-command deploy"

# Historical Release 0.8 reports may retain migrate release before deploy full — allowed.
for doc in \
  "$ROOT/docs/releases/RELEASE-0.8-ACCEPTANCE-REPORT.md" \
  "$ROOT/docs/operations/RELEASE-0.8-PRE-DEPLOY-PLAN.md" \
  "$ROOT/docs/releases/0.8-step-057-release-closure.md"
do
  grep -q 'migrate release' "$doc" || fail "$doc missing migrate release (historical OK)"
done
echo "OK: historical 0.8 docs retain migrate release evidence"

# --- 3. No deploy full followed by bare migrate in operator docs ---
python3 - <<'PY'
from pathlib import Path
import os, re, sys
root = Path(os.environ["ROOT"])
docs = [
    root / "docs/releases/0.8-step-057-release-closure.md",
    root / "docs/releases/RELEASE-0.8-ACCEPTANCE-REPORT.md",
    root / "docs/operations/POST-0.8-MACHINE-MIGRATION.md",
    root / "docs/operations/RELEASE-0.8-PRE-DEPLOY-PLAN.md",
    root / "docs/releases/RELEASE-CHECKLIST.md",
    root / "docs/RELEASE_ENGINEERING_WORKFLOW.md",
    root / "docs/DEPLOYMENT.md",
]
bad = re.compile(
    r"manage_deploy\.sh\s+deploy\s+full[\s\S]{0,500}?"
    r"manage_deploy\.sh\s+migrate(?!\s+(release|live)\b)",
    re.I,
)
bad2 = re.compile(
    r"separately approved[\s\S]{0,160}?manage_deploy\.sh\s+migrate(?!\s+(release|live)\b)",
    re.I,
)
for d in docs:
    text = d.read_text(encoding="utf-8")
    if bad.search(text) or bad2.search(text):
        print(f"FAIL: stale deploy-full→migrate sequence in {d}", file=sys.stderr)
        sys.exit(1)
print("OK: no deploy full → bare migrate in operator docs")
PY

# --- 4. Docs state deploy full runs internal / post-sync migration ---
for doc in \
  "$ROOT/docs/releases/RELEASE-CHECKLIST.md" \
  "$ROOT/docs/DEPLOYMENT.md" \
  "$ROOT/docs/RELEASE_ENGINEERING_WORKFLOW.md"
do
  grep -qiE 'post-sync|schema-first|run_migrations|idempotent' "$doc" \
    || fail "$doc must document deploy full migration ownership"
done
echo "OK: docs state deploy full migration ownership"

# --- 5–6. Bare migrate = /opt; migrate release = recovery schema-first ---
for doc in \
  "$ROOT/docs/releases/RELEASE-CHECKLIST.md" \
  "$ROOT/docs/DEPLOYMENT.md"
do
  grep -qiE '/opt.*(tree|install)|live /opt' "$doc" \
    || fail "$doc must document bare migrate as /opt-tree"
  grep -qi 'origin/main' "$doc" || fail "$doc must mention origin/main"
  grep -qi 'schema-first' "$doc" || fail "$doc must mention schema-first"
done
echo "OK: bare migrate=/opt and schema-first documented"

# --- Hard safety note present in historical pre-deploy + closure ---
for doc in \
  "$ROOT/docs/operations/RELEASE-0.8-PRE-DEPLOY-PLAN.md" \
  "$ROOT/docs/releases/0.8-step-057-release-closure.md"
do
  grep -q '0019_legacy_doc_type_canonical_enabled' "$doc" \
    || fail "$doc missing 0019 head requirement"
  grep -qiE 'STOP|Do not deploy|do not deploy' "$doc" \
    || fail "$doc missing STOP / do not deploy gate"
done
echo "OK: Release 0.8 hard safety note present (historical)"

# --- Stale-doc audit: no deploy→bare migrate ---
echo "--- stale-doc audit ---"
python3 - <<'PY'
from pathlib import Path
import os, re, sys
root = Path(os.environ["ROOT"])
patterns = [
    ("deploy full then bare migrate", re.compile(
        r"manage_deploy\.sh\s+deploy\s+full[\s\S]{0,500}?manage_deploy\.sh\s+migrate(?!\s+(release|live)\b)", re.I)),
    ("separately approved bare migrate", re.compile(
        r"separately approved[\s\S]{0,160}?manage_deploy\.sh\s+migrate(?!\s+(release|live)\b)", re.I)),
]
scan_dirs = [
    root / "docs/releases",
    root / "docs/operations",
    root / "docs",
]
hits = []
seen = set()
for base in scan_dirs:
    for path in sorted(base.glob("*.md") if base.name != "docs" else [base / "RELEASE_ENGINEERING_WORKFLOW.md", base / "DEPLOYMENT.md"]):
        if not path.is_file() or path in seen:
            continue
        seen.add(path)
        rel = str(path.relative_to(root))
        if not any(k in rel for k in (
            "0.8", "RELEASE-CHECKLIST", "RELEASE_ENGINEERING", "DEPLOYMENT",
            "POST-0.8", "PRE-DEPLOY", "RELEASE-0.8", "0.9-rollback",
            "RELEASE-ENGINEERING-HARDENING",
        )):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, rx in patterns:
            if rx.search(text):
                hits.append(f"{rel}: {label}")
if hits:
    print("REMAINING MATCHES:")
    for h in hits:
        print(" ", h)
    sys.exit(1)
print("No remaining stale deploy→migrate sequences in scanned operator docs")
PY

echo "OK: schema-first / one-command documentation regression passed"
