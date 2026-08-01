#!/usr/bin/env bash
# Internal migration decision for One Command deploy full.
# Outcomes: schema_first | post_sync_only  (return 0)
# Fail closed: return 1 (ambiguous / unreachable / multiple heads / live ahead)
set -euo pipefail

md_migration_list_files() {
  local versions_dir="$1"
  if [[ ! -d "$versions_dir" ]]; then
    echo ""
    return 0
  fi
  find "$versions_dir" -maxdepth 1 -type f -name '*.py' ! -name '__*' -printf '%f\n' 2>/dev/null | sort
}

md_migration_list_tip_files() {
  local repo="$1"
  local commit="$2"
  git -C "$repo" ls-tree -r --name-only "$commit" -- backend/migrations/versions/ \
    | awk -F/ '/\.py$/ && $NF !~ /^__/ {print $NF}' \
    | sort
}

md_migration_normalize_rev() {
  local raw="$1"
  echo "$raw" | head -1 | sed -E 's/[[:space:]]*\(.*\)[[:space:]]*$//; s/^[[:space:]]+//; s/[[:space:]]+$//'
}

# md_migration_decision repo commit project_root
# Sets: MD_MIGRATION_DECISION=schema_first|post_sync_only
md_migration_decision() {
  local repo="$1"
  local commit="$2"
  local project_root="${3:-/opt/ai-site-agent}"
  local opt_versions="$project_root/backend/migrations/versions"
  local live_env="$project_root/.env"
  local live_venv="$project_root/backend/.venv"

  MD_MIGRATION_DECISION=""
  MD_MIGRATION_DECISION_DETAIL=""
  MD_MIGRATION_TIP_HEAD=""

  # shellcheck source=deploy/lib/migrate_release.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/migrate_release.sh"

  local tip_files
  tip_files="$(md_migration_list_tip_files "$repo" "$commit")"
  if [[ -z "$tip_files" ]]; then
    MD_MIGRATION_DECISION_DETAIL="tip has no migration files"
    echo "ERROR: migration decision failed — tip has no migration files" >&2
    return 1
  fi

  if [[ ! -f "$live_env" ]]; then
    MD_MIGRATION_DECISION_DETAIL="live .env missing"
    echo "ERROR: migration decision failed — live .env missing at $live_env" >&2
    return 1
  fi
  if [[ ! -x "$live_venv/bin/alembic" ]]; then
    MD_MIGRATION_DECISION_DETAIL="live venv/alembic missing"
    echo "ERROR: migration decision failed — live venv/alembic required at $live_venv" >&2
    return 1
  fi

  md_migrate_release_load_database_url "$live_env" || {
    MD_MIGRATION_DECISION_DETAIL="database unreachable or DATABASE_URL unreadable"
    echo "ERROR: migration decision failed — cannot load DATABASE_URL" >&2
    return 1
  }

  local wt
  wt="$(mktemp -d /tmp/ai-site-agent-migdec-XXXXXX)"
  if ! git -C "$repo" worktree add --detach "$wt" "$commit" >/dev/null 2>&1; then
    rm -rf "$wt"
    MD_MIGRATION_DECISION_DETAIL="cannot create tip worktree"
    echo "ERROR: migration decision failed — cannot create tip worktree" >&2
    return 1
  fi

  local cleanup_wt
  cleanup_wt() {
    git -C "$repo" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
  }

  local heads tip_head live_raw live_rev
  set +e
  heads="$(md_migrate_release_heads "$wt/backend" 2>/dev/null)"
  local heads_rc=$?
  set -e
  if [[ "$heads_rc" -ne 0 || -z "$heads" ]]; then
    cleanup_wt
    MD_MIGRATION_DECISION_DETAIL="cannot read tip alembic heads"
    echo "ERROR: migration decision failed — cannot read tip alembic heads" >&2
    return 1
  fi
  local head_count
  head_count="$(echo "$heads" | grep -c . || true)"
  if [[ "$head_count" -ne 1 ]]; then
    cleanup_wt
    MD_MIGRATION_DECISION_DETAIL="incompatible multiple alembic heads in tip ($head_count)"
    echo "ERROR: migration decision failed — tip has $head_count alembic heads" >&2
    echo "$heads" >&2
    return 1
  fi
  tip_head="$(echo "$heads" | head -1)"
  MD_MIGRATION_TIP_HEAD="$tip_head"
  echo "[migrate-decision] tip_head=$tip_head"

  set +e
  live_raw="$(md_migrate_release_alembic "$wt/backend" "$live_venv" current 2>/dev/null | tail -1)"
  local live_rc=$?
  set -e
  if [[ "$live_rc" -ne 0 || -z "$live_raw" ]]; then
    cleanup_wt
    MD_MIGRATION_DECISION_DETAIL="database unreachable"
    echo "ERROR: migration decision failed — database unreachable (alembic current)" >&2
    return 1
  fi
  live_rev="$(md_migration_normalize_rev "$live_raw")"
  echo "[migrate-decision] live_revision=${live_rev:-<empty>}"

  # Live ahead / unknown: live revision must exist among tip revision ids.
  if [[ -n "$live_rev" ]]; then
    local tip_revs
    tip_revs="$(python3 - "$wt/backend" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1]) / "migrations" / "versions"
for p in sorted(root.glob("*.py")):
    if p.name.startswith("__"):
        continue
    rev = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("revision"):
            rev = line.split("=", 1)[1].strip().strip("\"'")
            break
    if rev:
        print(rev)
PY
)"
    if ! echo "$tip_revs" | grep -qxF "$live_rev"; then
      cleanup_wt
      MD_MIGRATION_DECISION_DETAIL="live DB revision ahead of or unknown to tip ($live_rev)"
      echo "ERROR: migration decision failed — live DB revision not in tip: $live_rev" >&2
      return 1
    fi
  fi

  cleanup_wt

  local missing=0 f
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if [[ ! -f "$opt_versions/$f" ]]; then
      echo "[migrate-decision] missing_on_opt=$f"
      missing=1
    fi
  done <<< "$tip_files"

  if [[ "$missing" -eq 1 ]]; then
    MD_MIGRATION_DECISION="schema_first"
    MD_MIGRATION_DECISION_DETAIL="tip migration files absent from /opt"
    echo "[migrate-decision] outcome=schema_first"
    return 0
  fi

  MD_MIGRATION_DECISION="post_sync_only"
  MD_MIGRATION_DECISION_DETAIL="/opt already contains tip migration files"
  echo "[migrate-decision] outcome=post_sync_only"
  return 0
}
