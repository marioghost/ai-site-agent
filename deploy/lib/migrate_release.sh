#!/usr/bin/env bash
# Schema-first release migration: Alembic from clean origin/main worktree
# against the live /opt database, without syncing code or restarting services.
#
# Public entry: bash deploy/manage_deploy.sh migrate release
set -euo pipefail

md_migrate_release_redact_url() {
  local url="${1:-}"
  # postgresql+psycopg://user:pass@host:port/db → user:***@host:port/db
  python3 -c '
import re, sys
u = sys.argv[1] if len(sys.argv) > 1 else ""
print(re.sub(r"(://[^:/@]+:)[^@]+@", r"\1***@", u))
' "$url"
}

md_migrate_release_db_name() {
  local url="${1:-}"
  python3 -c '
import sys
from urllib.parse import urlparse, unquote
u = sys.argv[1] if len(sys.argv) > 1 else ""
# SQLAlchemy URLs may use postgresql+psycopg://
u = u.replace("postgresql+psycopg://", "postgresql://", 1)
u = u.replace("postgresql+psycopg2://", "postgresql://", 1)
p = urlparse(u)
name = (p.path or "").lstrip("/")
print(name.split("?")[0])
' "$url"
}

md_migrate_release_load_database_url() {
  local env_file="$1"
  if [[ ! -f "$env_file" ]]; then
    echo "ERROR: live env missing: $env_file" >&2
    return 1
  fi
  # Read DATABASE_URL without sourcing the whole file into the shell.
  local url
  url="$(python3 - "$env_file" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
for line in path.read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if not s or s.startswith("#"):
        continue
    if s.startswith("DATABASE_URL="):
        val = s.split("=", 1)[1].strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        print(val)
        break
else:
    sys.exit(2)
PY
)" || {
    echo "ERROR: DATABASE_URL not found in $env_file" >&2
    return 1
  }
  if [[ -z "$url" || "$url" != postgresql* ]]; then
    echo "ERROR: DATABASE_URL must be a PostgreSQL URL" >&2
    return 1
  fi
  MD_MIGRATE_RELEASE_DATABASE_URL="$url"
}

md_migrate_release_alembic() {
  local backend_dir="$1"
  local venv_dir="$2"
  shift 2
  if [[ ! -x "$venv_dir/bin/alembic" ]]; then
    echo "ERROR: alembic missing in venv: $venv_dir" >&2
    return 1
  fi
  if [[ ! -f "$backend_dir/alembic.ini" ]]; then
    echo "ERROR: alembic.ini missing under $backend_dir" >&2
    return 1
  fi
  (
    cd "$backend_dir"
    export DATABASE_URL="$MD_MIGRATE_RELEASE_DATABASE_URL"
    "$venv_dir/bin/alembic" "$@"
  )
}

md_migrate_release_heads() {
  local backend_dir="$1"
  python3 - "$backend_dir" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1]) / "migrations" / "versions"
revs, downs = {}, {}
for p in root.glob("*.py"):
    rev = down = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("revision"):
            rev = line.split("=", 1)[1].strip().strip("\"'")
        if line.startswith("down_revision"):
            down = line.split("=", 1)[1].strip().strip("\"'")
            if down == "None":
                down = None
    if rev:
        revs[rev] = p.name
        downs[rev] = down
children = set(downs.values()) - {None}
heads = sorted(r for r in revs if r not in children)
print("\n".join(heads))
PY
}

md_migrate_release_verify_columns() {
  local venv_python="$1"
  "$venv_python" - <<'PY'
import os
import sys
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
engine = create_engine(url)
needed = ("allow_legacy_kp_presets", "legacy_doc_type_canonical_enabled")
with engine.connect() as conn:
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'settings' "
            "AND column_name IN "
            "('allow_legacy_kp_presets', 'legacy_doc_type_canonical_enabled')"
        )
    ).fetchall()
    found = {r[0] for r in rows}
    missing = [c for c in needed if c not in found]
    if missing:
        print("ERROR: missing settings columns: " + ", ".join(missing), file=sys.stderr)
        sys.exit(1)
    vals = conn.execute(
        text(
            "SELECT allow_legacy_kp_presets, legacy_doc_type_canonical_enabled "
            "FROM settings"
        )
    ).fetchall()
    for i, (a, b) in enumerate(vals):
        if a is not False or b is not False:
            print(
                f"ERROR: settings row {i} expected false/false, got {a!r}/{b!r}",
                file=sys.stderr,
            )
            sys.exit(1)
    print(f"OK: columns present; {len(vals)} settings row(s) both false")
PY
}

md_migrate_release_corpus_snapshot() {
  local venv_python="$1"
  local label="$2"
  "$venv_python" - <<PY
import os
from sqlalchemy import create_engine, text
url = os.environ["DATABASE_URL"]
engine = create_engine(url)
queries = {
    "sources": "SELECT COUNT(*) FROM sources",
    "chunks": "SELECT COUNT(*) FROM chunks",
    "claims": "SELECT COUNT(*) FROM claim",
    "observations": "SELECT COUNT(*) FROM observation_ref",
    "evidence_links": "SELECT COUNT(*) FROM evidence_link",
}
with engine.connect() as conn:
    parts = []
    for name, sql in queries.items():
        try:
            n = conn.execute(text(sql)).scalar()
            parts.append(f"{name}={n}")
        except Exception as exc:
            parts.append(f"{name}=UNAVAILABLE({type(exc).__name__})")
    print("$label: " + ", ".join(parts))
PY
}

# Main entry — no code sync, no service restart, no Qdrant calls.
md_migrate_release() {
  local assume_yes=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --yes|-y) assume_yes=1; shift ;;
      *)
        echo "ERROR: unknown migrate release argument: $1" >&2
        echo "Usage: bash deploy/manage_deploy.sh migrate release [--yes]" >&2
        return 1
        ;;
    esac
  done

  # shellcheck source=deploy/lib/deploy_source.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy_source.sh"
  # shellcheck source=deploy/lib/confirmation.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/confirmation.sh"

  md_deploy_source_init
  MD_MIGRATE_RELEASE_WORKTREE=""
  md_migrate_release_cleanup() {
    if [[ -n "${MD_MIGRATE_RELEASE_WORKTREE:-}" && -d "${MD_MIGRATE_RELEASE_WORKTREE}" ]]; then
      git -C "${MD_DEPLOY_REPO_ROOT}" worktree remove --force "${MD_MIGRATE_RELEASE_WORKTREE}" 2>/dev/null \
        || rm -rf "${MD_MIGRATE_RELEASE_WORKTREE}"
    fi
  }
  trap md_migrate_release_cleanup EXIT

  local repo="$MD_DEPLOY_REPO_ROOT"
  local live_root="$MD_DEPLOY_PROJECT_ROOT"
  local live_env="$live_root/.env"
  local live_venv="$live_root/backend/.venv"
  local report_dir="$live_root/logs"
  mkdir -p "$report_dir"
  local stamp
  stamp="$(date +%Y%m%d_%H%M%S)"
  local report="$report_dir/migrate-release-${stamp}.log"

  {
    echo "=== migrate release ==="
    echo "started: $(date -Is)"
  } | tee "$report"

  # Refuse emergency / legacy bypasses for this path entirely.
  if deploy_guard_emergency_enabled; then
    echo "ERROR: migrate release refuses emergency overrides" | tee -a "$report" >&2
    return 1
  fi
  deploy_guard_reject_legacy_bypasses || return 1

  deploy_guard_assert_not_detached "$repo" || return 1
  deploy_guard_assert_on_main_branch "$repo" || return 1
  deploy_guard_assert_clean_worktree "$repo" "operator checkout" || return 1
  deploy_guard_fetch_origin "$repo"
  deploy_guard_assert_local_main_matches_origin "$repo" || return 1

  local commit
  commit="$(deploy_guard_resolve_commit "$repo" "")"
  deploy_guard_assert_commit_on_main "$repo" "$commit" || return 1

  md_migrate_release_load_database_url "$live_env" || return 1
  local db_name redacted
  db_name="$(md_migrate_release_db_name "$MD_MIGRATE_RELEASE_DATABASE_URL")"
  redacted="$(md_migrate_release_redact_url "$MD_MIGRATE_RELEASE_DATABASE_URL")"

  {
    echo "origin/main_commit=$commit"
    echo "live_project_root=$live_root"
    echo "live_env=$live_env"
    echo "database_url_redacted=$redacted"
    echo "database_name=$db_name"
  } | tee -a "$report"

  if [[ "$db_name" == *recovery* ]]; then
    echo "ERROR: refusing migrate release against recovery database: $db_name" | tee -a "$report" >&2
    return 1
  fi

  if [[ "$assume_yes" -ne 1 ]]; then
    MD_ASSUME_YES=0
    if ! md_confirm "Apply Alembic from origin/main $commit to live DB '$db_name' (no /opt code sync, no restart)?" "n"; then
      echo "Aborted by operator" | tee -a "$report"
      return 1
    fi
  fi

  MD_MIGRATE_RELEASE_WORKTREE="$(mktemp -d /tmp/ai-site-agent-migrate-release-XXXXXX)"
  echo "migration_source_worktree=$MD_MIGRATE_RELEASE_WORKTREE" | tee -a "$report"
  git -C "$repo" worktree add --detach "$MD_MIGRATE_RELEASE_WORKTREE" "$commit" >/dev/null
  deploy_guard_assert_clean_worktree "$MD_MIGRATE_RELEASE_WORKTREE" "migrate-release worktree" || return 1

  local src_backend="$MD_MIGRATE_RELEASE_WORKTREE/backend"
  local opt_backend="$live_root/backend"
  if [[ ! -d "$src_backend/migrations/versions" ]]; then
    echo "ERROR: worktree missing migrations: $src_backend" | tee -a "$report" >&2
    return 1
  fi
  # Prove source is worktree, not live /opt tree.
  if [[ "$(realpath "$src_backend")" == "$(realpath "$opt_backend" 2>/dev/null || echo "")" ]]; then
    echo "ERROR: migration source resolved to live /opt backend — refuse" | tee -a "$report" >&2
    return 1
  fi
  echo "migration_source_backend=$src_backend" | tee -a "$report"
  echo "live_opt_backend_not_used=$opt_backend" | tee -a "$report"

  local heads
  heads="$(md_migrate_release_heads "$src_backend")"
  echo "repository_alembic_heads:" | tee -a "$report"
  echo "$heads" | tee -a "$report"
  if [[ "$(echo "$heads" | wc -l)" -ne 1 ]]; then
    echo "ERROR: expected exactly one Alembic head in origin/main source" | tee -a "$report" >&2
    return 1
  fi
  local target_head
  target_head="$(echo "$heads" | head -1)"
  echo "target_head=$target_head" | tee -a "$report"

  if [[ ! -x "$live_venv/bin/python" || ! -x "$live_venv/bin/alembic" ]]; then
    echo "ERROR: live venv/alembic required at $live_venv (do not invent a new venv here)" | tee -a "$report" >&2
    return 1
  fi

  export DATABASE_URL="$MD_MIGRATE_RELEASE_DATABASE_URL"

  local pre_rev
  pre_rev="$(md_migrate_release_alembic "$src_backend" "$live_venv" current 2>/dev/null | tail -1 || true)"
  echo "pre_revision=${pre_rev:-<unknown>}" | tee -a "$report"

  echo "corpus_before:" | tee -a "$report"
  md_migrate_release_corpus_snapshot "$live_venv/bin/python" "before" | tee -a "$report" || true

  echo "NOTE: no Qdrant commands are invoked by migrate release" | tee -a "$report"

  set +e
  md_migrate_release_alembic "$src_backend" "$live_venv" upgrade head 2>&1 | tee -a "$report"
  local mig_rc=${PIPESTATUS[0]}
  set -e
  echo "migrate_exit_code=$mig_rc" | tee -a "$report"

  if [[ "$mig_rc" -ne 0 ]]; then
    echo "ERROR: migrate release FAILED — no deploy/sync/restart performed" | tee -a "$report" >&2
    echo "ERROR: do not use manual SQL; do not auto-downgrade; stop for operator review" | tee -a "$report" >&2
    return "$mig_rc"
  fi

  local post_rev
  post_rev="$(md_migrate_release_alembic "$src_backend" "$live_venv" current 2>/dev/null | tail -1 || true)"
  echo "post_revision=${post_rev:-<unknown>}" | tee -a "$report"
  if [[ "$post_rev" != "$target_head" && "$post_rev" != *"$target_head"* ]]; then
    echo "ERROR: post revision ($post_rev) != target head ($target_head)" | tee -a "$report" >&2
    return 1
  fi

  md_migrate_release_verify_columns "$live_venv/bin/python" 2>&1 | tee -a "$report" || return 1

  echo "corpus_after:" | tee -a "$report"
  md_migrate_release_corpus_snapshot "$live_venv/bin/python" "after" | tee -a "$report" || true

  echo "verification=PASS" | tee -a "$report"
  echo "services_restarted=no" | tee -a "$report"
  echo "opt_code_synced=no" | tee -a "$report"
  echo "qdrant_touched=no" | tee -a "$report"
  echo "report_path=$report" | tee -a "$report"
  echo "OK: migrate release complete ($pre_rev → $post_rev)" | tee -a "$report"
  return 0
}
