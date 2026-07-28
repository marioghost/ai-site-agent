#!/usr/bin/env bash
# Regression: Release 0.8 operator docs + help stay schema-first aligned.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MD="$ROOT/deploy/manage_deploy.sh"
export ROOT
fail() { echo "FAIL: $*" >&2; exit 1; }

# --- 1. Help distinguishes migrate / migrate live / migrate release ---
help_out="$(bash "$MD" help 2>&1 || true)"
echo "$help_out" | grep -qE '^[[:space:]]*migrate[[:space:]]' \
  || fail "help missing bare migrate"
echo "$help_out" | grep -q 'migrate live' || fail "help missing migrate live"
echo "$help_out" | grep -q 'migrate release' || fail "help missing migrate release"
echo "$help_out" | grep -qi 'alias of bare migrate' \
  || fail "help must say migrate live is alias of bare migrate"
echo "$help_out" | grep -qi 'live /opt' || fail "help must say bare migrate uses /opt tree"
echo "$help_out" | grep -qi 'origin/main' || fail "help must mention origin/main for migrate release"
echo "$help_out" | grep -qiE 'idempotent|defense-in-depth|post-sync Alembic' \
  || fail "help must document deploy full post-sync Alembic no-op"
echo "$help_out" | grep -qi 'only supported schema-first' \
  || fail "help must say migrate release is only schema-first command"
echo "OK: help distinguishes migrate commands + post-sync policy"

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

# --- 2. Canonical sequence in primary Release 0.8 operator docs ---
for doc in \
  "$ROOT/docs/releases/RELEASE-CHECKLIST.md" \
  "$ROOT/docs/operations/RELEASE-0.8-PRE-DEPLOY-PLAN.md" \
  "$ROOT/docs/releases/0.8-step-057-release-closure.md"
do
  python3 - "$doc" <<'PY' || exit 1
import pathlib, re, sys
text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
pat = re.compile(
    r"status\s*→\s*backup db\s*→\s*migrate release\s*→\s*verify schema head\s*→\s*deploy full"
    r"\s*→\s*health\s*→\s*build-info\s*→\s*smoke\s*→\s*verify-release",
    re.I | re.S,
)
pat2 = re.compile(
    r"status\s*\n\s*→\s*backup db\s*\n\s*→\s*migrate release\s*\n\s*→\s*verify schema head"
    r"\s*\n\s*→\s*deploy full\s*\n\s*→\s*health\s*\n\s*→\s*build-info"
    r"\s*\n\s*→\s*smoke\s*\n\s*→\s*verify-release",
    re.I,
)
if not (pat.search(text) or pat2.search(text)):
    print(f"FAIL: {sys.argv[1]} missing canonical Release 0.8 sequence", file=sys.stderr)
    sys.exit(1)
PY
  grep -q 'migrate release' "$doc" || fail "$doc missing migrate release"
done

# Acceptance + POST-0.8 + workflow must mention migrate release before deploy full intent
for doc in \
  "$ROOT/docs/releases/RELEASE-0.8-ACCEPTANCE-REPORT.md" \
  "$ROOT/docs/operations/POST-0.8-MACHINE-MIGRATION.md" \
  "$ROOT/docs/RELEASE_ENGINEERING_WORKFLOW.md"
do
  grep -q 'migrate release' "$doc" || fail "$doc missing migrate release"
  python3 - "$doc" <<'PY' || exit 1
import pathlib, sys
text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").lower()
i_mr = text.find("migrate release")
i_df = text.find("deploy full")
if i_mr < 0 or i_df < 0:
    print(f"FAIL: {sys.argv[1]} missing migrate release or deploy full", file=sys.stderr)
    sys.exit(1)
# First substantive migrate release should appear before a deploy full used in the cutover recipe.
# Accept if migrate release appears at least once before the last deploy full.
if text.rfind("deploy full") < i_mr and i_mr > i_df:
    # Still OK if an earlier migrate release exists before some deploy full
    if not any(text.find("migrate release", 0, pos) >= 0 for pos in [i for i in range(len(text)) if text.startswith("deploy full", i)][:5]):
        pass
# Require at least one migrate release occurrence before the first deploy full in acceptance-style recipes
first_block = text
# Prefer: backup db then migrate release then deploy full order somewhere
if "migrate release" in first_block and "deploy full" in first_block:
    # Find a window containing both in correct order
    ok = False
    start = 0
    while True:
        a = first_block.find("migrate release", start)
        if a < 0:
            break
        b = first_block.find("deploy full", a)
        if b > a:
            ok = True
            break
        start = a + 1
    if not ok:
        print(f"FAIL: {sys.argv[1]} has no migrate release before deploy full", file=sys.stderr)
        sys.exit(1)
PY
done
echo "OK: Release 0.8 docs use migrate release before deploy full"

# --- 3. No deploy full followed by bare migrate in Release 0.8 operator docs ---
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
print("OK: no deploy full → bare migrate in Release 0.8 operator docs")
PY

# --- 4. Docs state deploy full still runs internal idempotent migration ---
for doc in \
  "$ROOT/docs/releases/RELEASE-CHECKLIST.md" \
  "$ROOT/docs/operations/RELEASE-0.8-PRE-DEPLOY-PLAN.md" \
  "$ROOT/docs/DEPLOYMENT.md" \
  "$ROOT/docs/RELEASE_ENGINEERING_WORKFLOW.md"
do
  grep -qiE 'run_migrations|post-sync|idempotent|defense-in-depth' "$doc" \
    || fail "$doc must document deploy full internal/post-sync migration"
done
echo "OK: docs state deploy full internal idempotent migration"

# --- 5–6. Bare migrate = /opt; migrate release = origin/main schema-first ---
for doc in \
  "$ROOT/docs/releases/RELEASE-CHECKLIST.md" \
  "$ROOT/docs/operations/RELEASE-0.8-PRE-DEPLOY-PLAN.md" \
  "$ROOT/docs/DEPLOYMENT.md"
do
  grep -qiE '/opt.*(tree|install)|live /opt' "$doc" \
    || fail "$doc must document bare migrate as /opt-tree"
  grep -qi 'origin/main' "$doc" || fail "$doc must mention origin/main for migrate release"
  grep -qi 'schema-first' "$doc" || fail "$doc must mention schema-first"
done
echo "OK: bare migrate=/opt and migrate release=origin/main schema-first documented"

# --- Hard safety note present in pre-deploy + closure ---
for doc in \
  "$ROOT/docs/operations/RELEASE-0.8-PRE-DEPLOY-PLAN.md" \
  "$ROOT/docs/releases/0.8-step-057-release-closure.md"
do
  grep -q '0019_legacy_doc_type_canonical_enabled' "$doc" \
    || fail "$doc missing 0019 head requirement"
  grep -qiE 'STOP|Do not deploy|do not deploy' "$doc" \
    || fail "$doc missing STOP / do not deploy gate"
done
echo "OK: Release 0.8 hard safety note present"

# --- Policy limitation honesty ---
grep -qiE 'hard-block|does not yet refuse|does \*\*not\*\* yet refuse|does not yet' \
  "$ROOT/docs/operations/RELEASE-0.8-PRE-DEPLOY-PLAN.md" \
  || fail "pre-deploy must state CLI does not hard-block deploy full"
echo "OK: policy vs hard enforcement documented"

# --- Stale-doc audit across operator-related docs ---
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
        name = path.name
        rel = str(path.relative_to(root))
        # Focus on Release 0.8 / deploy / workflow operator docs
        if not any(k in rel for k in (
            "0.8", "RELEASE-CHECKLIST", "RELEASE_ENGINEERING", "DEPLOYMENT",
            "POST-0.8", "PRE-DEPLOY", "RELEASE-0.8",
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

echo "OK: schema-first documentation regression passed"
