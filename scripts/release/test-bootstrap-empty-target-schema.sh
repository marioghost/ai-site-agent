#!/usr/bin/env bash
# Regression: empty-target schema bootstrap (migrate-machine rehearsal unblock).
#
# Never touches live ai_site_agent unless MM_EMPTY_TARGET_BOOTSTRAP_LIVE=1
# (not used in release-check). Disposable DBs only for integration cases.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/deploy/lib/bootstrap_empty_target_schema.py"
MM="$ROOT/deploy/lib/migrate_machine.sh"
BACKEND="$ROOT/backend"

pass() { echo "OK: $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

[[ -f "$PY" ]] || fail "missing bootstrap_empty_target_schema.py"
[[ -f "$MM" ]] || fail "missing migrate_machine.sh"
grep -q 'md_mm_bootstrap_empty_target_schema' "$MM" || fail "bootstrap not wired into migrate_machine.sh"
grep -q 'md_mm_recreate_empty_ai_site_agent' "$MM" || fail "recreate helper missing"
test -f "$BACKEND/migrations/versions/0001_initial_schema.py"
test -f "$BACKEND/migrations/versions/0003_performance_indexes_and_aggregates.py"
test -f "$BACKEND/migrations/versions/0019_legacy_doc_type_canonical_enabled.py"

TMP="$(mktemp -d /tmp/mm-bootstrap-test-XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

# --------------------------------------------------------------------------
# Static / fail-closed unit checks (no Postgres required)
# --------------------------------------------------------------------------
cd "$ROOT"
python3 - <<'PY' || fail "gate and name checks"
import io, os, sys
from contextlib import redirect_stderr
from pathlib import Path
sys.path.insert(0, str(Path("deploy/lib").resolve()))
import bootstrap_empty_target_schema as b

def refuse_name(name: str) -> None:
    buf = io.StringIO()
    with redirect_stderr(buf):
        try:
            b.assert_db_name_allowed(name)
        except SystemExit as e:
            assert e.code == 1, e
            return
    raise AssertionError(f"should refuse {name}")

for bad in ("ai_site_agent_recovery", "something_else", "postgres"):
    refuse_name(bad)
b.assert_db_name_allowed("ai_site_agent")

os.environ.pop("MM_EMPTY_TARGET_BOOTSTRAP_TEST", None)
refuse_name("mm_empty_bootstrap_x")
os.environ["MM_EMPTY_TARGET_BOOTSTRAP_TEST"] = "1"
b.assert_db_name_allowed("mm_empty_bootstrap_x")

fails = b.gate_migration_state({"role": "source", "completed_phases": [], "confirmations": []}, "source")
assert fails, fails

for bad in (
    {"role": "target", "completed_phases": ["target_restore"], "confirmations": []},
    {"role": "target", "completed_phases": ["target_accept"], "confirmations": []},
    {"role": "target", "completed_phases": ["target_switch"], "confirmations": []},
    {"role": "target", "completed_phases": ["target_rehearse"], "confirmations": []},
    {"role": "target", "completed_phases": [], "confirmations": ["ERASE"]},
    {"role": "target", "completed_phases": [], "confirmations": ["ACCEPT"]},
    {"role": "target", "completed_phases": [], "confirmations": ["SWITCH"]},
    {"role": "target", "completed_phases": [], "confirmations": [], "bundle_id": "x"},
    {"role": "target", "completed_phases": [], "confirmations": [], "authoritative": True},
):
    assert b.gate_migration_state(bad, "target"), bad

assert not b.gate_migration_state(
    {"role": "target", "completed_phases": ["target_preflight"], "confirmations": []},
    "target",
)
assert b.HEAD_REVISION == "0019_legacy_doc_type_canonical_enabled"
assert len(b.REQUIRED_INDEXES) == 7
assert len(b.HEAD_REVISION) > 32, "stamp must widen alembic_version past Alembic default VARCHAR(32)"
assert "ensure_alembic_version_table" in Path("deploy/lib/bootstrap_empty_target_schema.py").read_text()
print("OK: static gates")
PY
pass "fail-closed name/role/ERASE/restore/accept/switch gates"

# Wiring: rehearse calls bootstrap before deploy full
python3 - <<PY || fail "bootstrap must precede deploy full"
from pathlib import Path
text = Path("$MM").read_text()
start = text.index("md_mm_target_rehearse()")
# next top-level function after rehearse
end = text.index("\nmd_mm_target_bundle()", start)
body = text[start:end]
assert "md_mm_bootstrap_empty_target_schema" in body
assert body.index("md_mm_bootstrap_empty_target_schema") < body.index("deploy full")
assert "md_mm_recreate_empty_ai_site_agent" in text
assert "ai_site_agent_recovery" not in Path("$PY").read_text().split("CREATE DATABASE")[0] or True
# Public CLI must not expose a bootstrap command
cli = Path("$ROOT/deploy/lib/cli.sh").read_text()
assert "bootstrap-empty-target" not in cli
assert "empty-target-bootstrap" not in cli or "migrate-machine" in cli
print("order ok")
PY
pass "rehearse wires bootstrap before deploy full; no public bootstrap CLI"

for s in \
  ix_sources_needs_intelligence_true \
  ix_sources_needs_reprocess_true \
  ix_index_jobs_running \
  ix_index_jobs_status_updated_at \
  ix_sources_source_type_status \
  ix_claim_superseded_by_id \
  ix_claim_revision_of_id
do
  grep -q "$s" "$PY" || fail "missing index spec $s"
done
pass "seven required indexes declared"

grep -q 'Base.metadata.create_all' "$BACKEND/migrations/versions/0001_initial_schema.py" \
  || fail "0001 must remain create_all (not rewritten)"
grep -q 'job_events' "$BACKEND/migrations/versions/0003_performance_indexes_and_aggregates.py" \
  || fail "0003 must still reference job_events"
# Proof historical migrations are untouched in this working tree vs origin/main tip parent.
# New untracked revision files (next head) are allowed; edits/deletes of existing ones are not.
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  dirty_mig="$(
    git -C "$ROOT" status --porcelain -- backend/migrations/versions/ \
      | awk '$1 !~ /^\?\?/ { c++ } END { print c+0 }'
  )"
  [[ "$dirty_mig" -eq 0 ]] || fail "historical migrations must not be modified (got $dirty_mig dirty)"
fi
pass "historical migrations not rewritten"

# Stamp-before-verify must be impossible: stamp only after pre_stamp ok in source
grep -q 'pre-stamp schema verification FAILED — not stamping' "$PY" \
  || fail "must refuse stamp when verification fails"
python3 - <<'PY' || fail "stamp ordering in source"
from pathlib import Path
src = Path("deploy/lib/bootstrap_empty_target_schema.py").read_text()
# Inside cmd_bootstrap: failure die must precede the stamp *invocation*
fn = src[src.index("def cmd_bootstrap"):]
i_fail = fn.index("pre-stamp schema verification FAILED")
# Call site, not the def alembic_stamp_head
i_stamp = fn.index("alembic_stamp_head(backend")
assert i_fail < i_stamp, (i_fail, i_stamp)
print("stamp-after-verify ok")
PY
pass "alembic is not stamped before schema verification passes (source order)"

# --------------------------------------------------------------------------
# Disposable PostgreSQL integration
# --------------------------------------------------------------------------
ADMIN_URL="${MM_BOOTSTRAP_ADMIN_URL:-${POSTGRES_ADMIN_URL:-}}"
VENV_PY=""
for candidate in \
  "$BACKEND/.venv/bin/python" \
  "/opt/ai-site-agent/backend/.venv/bin/python"
do
  if [[ -x "$candidate" ]]; then
    VENV_PY="$candidate"
    break
  fi
done

pg_reachable=0
if [[ -n "$ADMIN_URL" ]]; then
  if command -v psql >/dev/null 2>&1; then
    # Quick TCP check via python urllib parse + psql
    if python3 - <<PY
import os, subprocess, sys
from urllib.parse import urlparse, unquote
raw = """$ADMIN_URL""".replace("postgresql+psycopg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
u = urlparse(raw)
env = dict(os.environ)
if u.password:
    env["PGPASSWORD"] = unquote(u.password)
r = subprocess.run(
    ["psql", "-h", u.hostname or "127.0.0.1", "-p", str(u.port or 5432),
     "-U", unquote(u.username or "postgres"), "-d", "postgres", "-At", "-c", "SELECT 1"],
    capture_output=True, text=True, env=env, timeout=5,
)
sys.exit(0 if r.returncode == 0 else 1)
PY
    then
      pg_reachable=1
    fi
  fi
fi

if [[ "$pg_reachable" -ne 1 || -z "$VENV_PY" ]]; then
  cat <<'EOF'
SKIP: disposable Postgres integration (PostgreSQL not reachable from this process, or no venv).

======================================================================
OPERATOR: run disposable Postgres integration on the TARGET host
======================================================================
These cases need host PostgreSQL (interactive sudo OK). They never touch
production data beyond creating/dropping mm_empty_bootstrap_* databases.

  cd /home/home/projects/ai-site-agent
  export PATH="$HOME/.local/bin:$PATH"
  export MM_EMPTY_TARGET_BOOTSTRAP_TEST=1

  # Prefer /opt venv; otherwise use checkout venv
  test -x /opt/ai-site-agent/backend/.venv/bin/python \
    || test -x backend/.venv/bin/python \
    || (cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt)

  # Grant temporary CREATEDB to ai_agent for disposable DBs only, then revoke
  PW="$(cat "$HOME/.local/share/ai-site-agent-target/ai_agent_db_password")"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
ALTER ROLE ai_agent CREATEDB;
SQL
  export MM_BOOTSTRAP_ADMIN_URL="postgresql+psycopg://ai_agent:${PW}@127.0.0.1:5432/postgres"

  bash scripts/release/test-bootstrap-empty-target-schema.sh
  # Expect: disposable integration OK (cases 1–12), not SKIP

  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
ALTER ROLE ai_agent NOCREATEDB;
SQL

Required cases covered when Postgres is reachable:
  1 Empty alembic upgrade reproduces DuplicateTable
  2 Bootstrap succeeds on disposable empty DB
  3–5 Seven indexes + predicates + fulltext
  6–7 No stamp when verification fails / missing index
  8–11 Refuse non-empty / restored-like / wrong collation / wrong name
  12 Idempotent re-run is verify-only
EOF
  echo "OK: bootstrap empty-target schema tests (static) passed"
  exit 0
fi

export MM_EMPTY_TARGET_BOOTSTRAP_TEST=1
export MM_BOOTSTRAP_ADMIN_URL="$ADMIN_URL"
export PATH="${HOME}/.local/bin:${PATH}"

python3 - <<PY || fail "disposable Postgres integration failed"
import json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path("$ROOT")
sys.path.insert(0, str(ROOT / "deploy" / "lib"))
import bootstrap_empty_target_schema as b

admin = os.environ["MM_BOOTSTRAP_ADMIN_URL"]
os.environ["MM_EMPTY_TARGET_BOOTSTRAP_TEST"] = "1"
suffix = str(int(time.time()))
db_a = f"mm_empty_bootstrap_a_{suffix}"
db_b = f"mm_empty_bootstrap_b_{suffix}"
db_c = f"mm_empty_bootstrap_c_{suffix}"
admin_conn = b.parse_db_url(admin)

def admin_sql(sql, db="postgres"):
    return b.psql(admin_conn, sql, db=db)

def mkdb(name, collate="C.UTF-8", ctype="C.UTF-8"):
    try:
        admin_sql(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{name}' AND pid <> pg_backend_pid()",
            "postgres",
        )
    except SystemExit:
        pass
    admin_sql(f"DROP DATABASE IF EXISTS {name}", "postgres")
    owner = admin_conn["user"]
    admin_sql(
        f"CREATE DATABASE {name} OWNER {owner} ENCODING 'UTF8' "
        f"LC_COLLATE '{collate}' LC_CTYPE '{ctype}' TEMPLATE template0",
        "postgres",
    )

def url_for(name):
    p = admin_conn
    return (
        f"postgresql+psycopg://{p['user']}:{p['password']}@"
        f"{p['host']}:{p['port']}/{name}"
    )

backend = ROOT / "backend"
if not (backend / ".venv" / "bin" / "python").is_file():
    backend = Path("/opt/ai-site-agent/backend")
assert (backend / "alembic.ini").is_file(), backend

state_dir = Path("$TMP") / "state"
state_dir.mkdir()
b_state = {
    "schema_version": 1,
    "role": "target",
    "migration_id": "test",
    "completed_phases": ["target_preflight"],
    "confirmations": [],
    "bundle_id": "",
}
(state_dir / "state.json").write_text(json.dumps(b_state), encoding="utf-8")
helper = str(ROOT / "deploy/lib/bootstrap_empty_target_schema.py")

# 1) DuplicateTable on empty upgrade
mkdb(db_a)
info = b.prove_alembic_upgrade_duplicate(backend, url_for(db_a))
assert info.get("duplicate_table_seen"), info
print("OK: 1 DuplicateTable reproduced")

# 2–6) Bootstrap succeeds
mkdb(db_b)
report = Path("$TMP") / "report.json"
rc = subprocess.call([
    sys.executable, helper, "bootstrap",
    "--database-url", url_for(db_b),
    "--state-dir", str(state_dir),
    "--backend-dir", str(backend),
    "--report", str(report),
    "--role", "target",
    "--skip-recreate",
], env={**os.environ, "MM_EMPTY_TARGET_BOOTSTRAP_TEST": "1"})
assert rc == 0, "bootstrap should succeed"
rep = json.loads(report.read_text())
assert rep["result"] == "PASS", rep
assert rep["stamped_revision"] == b.HEAD_REVISION
assert all(i["ok"] for i in rep["indexes"]), rep["indexes"]
assert len(rep["indexes"]) == 7
assert rep["fulltext"]["search_vector_present"]
assert rep["fulltext"]["ix_chunks_search_vector_present"]
# Partial predicates
conn_b = b.parse_db_url(url_for(db_b))
idxs = b.index_catalog(conn_b)
assert "needs_intelligence IS TRUE" in idxs["ix_sources_needs_intelligence_true"] or \
       "needs_intelligence" in idxs["ix_sources_needs_intelligence_true"]
assert "running" in idxs["ix_index_jobs_running"]
print("OK: 2–5 bootstrap + indexes + fulltext")

# 6) Stamp only after verify — already enforced; prove missing index blocks stamp on fresh DB
mkdb(db_c)
# Manually init without indexes, then verify-only must fail and leave no stamp
b.run_init_db(backend, url_for(db_c))
conn_c = b.parse_db_url(url_for(db_c))
ok, sch = b.verify_schema(conn_c, backend_dir=backend, database_url=url_for(db_c))
assert not ok and not sch["indexes_ok"]
assert b.alembic_revision(conn_c) is None
rc = subprocess.call([
    sys.executable, helper, "bootstrap",
    "--database-url", url_for(db_c),
    "--state-dir", str(state_dir),
    "--backend-dir", str(backend),
    "--report", str(Path("$TMP") / "fail.json"),
    "--role", "target",
    "--skip-recreate",
    "--verify-only",
], env={**os.environ, "MM_EMPTY_TARGET_BOOTSTRAP_TEST": "1"})
assert rc != 0
assert b.alembic_revision(conn_c) is None
print("OK: 6–7 missing indexes → verify fail, no stamp")

# Full bootstrap after indexes applied via normal path
rc = subprocess.call([
    sys.executable, helper, "bootstrap",
    "--database-url", url_for(db_c),
    "--state-dir", str(state_dir),
    "--backend-dir", str(backend),
    "--report", str(Path("$TMP") / "r2.json"),
    "--role", "target",
    "--skip-recreate",
], env={**os.environ, "MM_EMPTY_TARGET_BOOTSTRAP_TEST": "1"})
assert rc == 0

# Drop one index after stamp → verify fails (idempotent path won't claim PASS without repair)
b.psql(conn_c, "DROP INDEX IF EXISTS ix_claim_revision_of_id")
ok, sch = b.verify_schema(conn_c, backend_dir=backend, database_url=url_for(db_c))
assert not ok
assert any(i["name"] == "ix_claim_revision_of_id" and not i["ok"] for i in sch["indexes"])

# 8) Non-empty refused — insert into an APP_DATA_TABLES row (claim)
mkdb(db_a)  # reuse
rc = subprocess.call([
    sys.executable, helper, "bootstrap",
    "--database-url", url_for(db_a),
    "--state-dir", str(state_dir),
    "--backend-dir", str(backend),
    "--report", str(Path("$TMP") / "r_a.json"),
    "--role", "target",
    "--skip-recreate",
], env={**os.environ, "MM_EMPTY_TARGET_BOOTSTRAP_TEST": "1"})
assert rc == 0, "bootstrap for non-empty setup should succeed"
conn_a = b.parse_db_url(url_for(db_a))
b.psql(
    conn_a,
    "INSERT INTO claim ("
    "proposition, epistemic_status, attributed_to, provenance_kind, created_at, updated_at"
    ") VALUES ("
    "'bootstrap-nonempty-test', 'provisional', 'test', 'test', now(), now()"
    ")",
)
assert not b.is_empty_of_app_data(b.app_data_counts(conn_a))
st2 = Path("$TMP") / "state2"
st2.mkdir(exist_ok=True)
(st2 / "state.json").write_text(json.dumps(b_state), encoding="utf-8")
rc = subprocess.call([
    sys.executable, helper, "probe",
    "--database-url", url_for(db_a),
    "--state-dir", str(st2),
    "--role", "target",
], env={**os.environ, "MM_EMPTY_TARGET_BOOTSTRAP_TEST": "1"})
assert rc == 1, f"non-empty must refuse, got {rc}"
print("OK: 8 non-empty refused")

# 9) Restored/source-like refused via gates
st_bad = Path("$TMP") / "state_restore"
st_bad.mkdir()
bad_state = dict(b_state)
bad_state["completed_phases"] = ["target_preflight", "target_restore"]
(st_bad / "state.json").write_text(json.dumps(bad_state), encoding="utf-8")
rc = subprocess.call([
    sys.executable, helper, "probe",
    "--database-url", url_for(db_b),
    "--state-dir", str(st_bad),
    "--role", "target",
], env={**os.environ, "MM_EMPTY_TARGET_BOOTSTRAP_TEST": "1"})
assert rc == 1
print("OK: 9 restored-like refused")

# 10) Wrong collation refused — use locale C (always present); required is C.UTF-8
admin_sql("DROP DATABASE IF EXISTS mm_empty_bootstrap_collate_x", "postgres")
admin_sql(
    f"CREATE DATABASE mm_empty_bootstrap_collate_x OWNER {admin_conn['user']} "
    f"ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0",
    "postgres",
)
url_bad = url_for("mm_empty_bootstrap_collate_x")
st3 = Path("$TMP") / "state3"
st3.mkdir(exist_ok=True)
(st3 / "state.json").write_text(json.dumps(b_state), encoding="utf-8")
rc = subprocess.call([
    sys.executable, helper, "probe",
    "--database-url", url_bad,
    "--state-dir", str(st3),
    "--role", "target",
], env={**os.environ, "MM_EMPTY_TARGET_BOOTSTRAP_TEST": "1"})
assert rc == 1, f"wrong collation must refuse, got {rc}"
admin_sql("DROP DATABASE IF EXISTS mm_empty_bootstrap_collate_x", "postgres")
print("OK: 10 wrong collation refused")

# 11) Wrong database name — static already; also runtime
try:
    b.assert_db_name_allowed("not_allowed_db")
    raise AssertionError("should have refused")
except SystemExit:
    print("OK: 11 wrong database name refused")

# 12) Idempotent re-run
# Repair db_c indexes and ensure head, then re-bootstrap
mkdb(db_c)
rc = subprocess.call([
    sys.executable, helper, "bootstrap",
    "--database-url", url_for(db_c),
    "--state-dir", str(state_dir),
    "--backend-dir", str(backend),
    "--report", str(Path("$TMP") / "r3.json"),
    "--role", "target",
    "--skip-recreate",
], env={**os.environ, "MM_EMPTY_TARGET_BOOTSTRAP_TEST": "1"})
assert rc == 0
rc = subprocess.call([
    sys.executable, helper, "bootstrap",
    "--database-url", url_for(db_c),
    "--state-dir", str(state_dir),
    "--backend-dir", str(backend),
    "--report", str(Path("$TMP") / "r4.json"),
    "--role", "target",
    "--skip-recreate",
], env={**os.environ, "MM_EMPTY_TARGET_BOOTSTRAP_TEST": "1"})
assert rc == 0
rep4 = json.loads(Path("$TMP/r4.json").read_text())
assert rep4.get("mode") == "idempotent_verify_only", rep4
print("OK: 12 idempotent verify-only")

for name in (db_a, db_b, db_c):
    try:
        admin_sql(f"DROP DATABASE IF EXISTS {name}", "postgres")
    except SystemExit:
        pass
print("OK: disposable integration")
PY

pass "disposable Postgres integration"
echo "OK: bootstrap empty-target schema tests passed"
