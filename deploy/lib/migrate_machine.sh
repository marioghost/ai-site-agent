#!/usr/bin/env bash
# One-command machine migration orchestrator.
#
# Public entry: bash deploy/manage_deploy.sh migrate-machine
#
# The operator remembers one command. This file owns ordering, role detection,
# and interpretation only. Backup, deploy, migration, and verification are
# delegated to the existing production commands — never reimplemented here.
set -euo pipefail

MD_MM_CMD='bash deploy/manage_deploy.sh migrate-machine'
MD_MM_QDRANT_COLLECTIONS=(site_knowledge site_knowledge_answer_cache)
MD_MM_MODELS=(bge-m3 qwen2.5:3b)

# --------------------------------------------------------------------------
# failure shape — exactly four fields, nothing else
# --------------------------------------------------------------------------
md_mm_fail() {
  local code="$1" what="$2" why="$3" fix="$4"
  echo ""
  echo "MIGRATION STOPPED"
  echo ""
  printf 'WHAT FAILED   %s\n' "$what"
  printf 'WHY           %s\n' "$why"
  printf 'HOW TO FIX    %s\n' "$fix"
  printf 'RUN AGAIN     %s\n' "$MD_MM_CMD"
  echo ""
  if [[ -n "${MD_MM_DIR:-}" && -f "$MD_MM_DIR/state.json" ]]; then
    md_mm_py state-set --dir "$MD_MM_DIR" "last_error_code=$code" 2>/dev/null || true
  fi
  return 1
}

# Preflight accumulates independent read-only failures and reports them together.
MD_MM_PF_WHAT=()
MD_MM_PF_WHY=()
MD_MM_PF_FIX=()
MD_MM_PF_CODE=()

md_mm_pf_reset() { MD_MM_PF_WHAT=(); MD_MM_PF_WHY=(); MD_MM_PF_FIX=(); MD_MM_PF_CODE=(); }

md_mm_pf_add() {
  MD_MM_PF_CODE+=("$1"); MD_MM_PF_WHAT+=("$2"); MD_MM_PF_WHY+=("$3"); MD_MM_PF_FIX+=("$4")
}

md_mm_pf_ok() { echo "  OK   $1"; }

md_mm_pf_report() {
  local n=${#MD_MM_PF_WHAT[@]}
  if [[ "$n" -eq 0 ]]; then
    return 0
  fi
  echo ""
  echo "MIGRATION STOPPED"
  echo ""
  echo "$n preflight check(s) failed. All are independent and read-only —"
  echo "fix them in any order, then run the command again."
  local i
  for ((i = 0; i < n; i++)); do
    echo ""
    printf 'WHAT FAILED   %s\n' "${MD_MM_PF_WHAT[$i]}"
    printf 'WHY           %s\n' "${MD_MM_PF_WHY[$i]}"
    printf 'HOW TO FIX    %s\n' "${MD_MM_PF_FIX[$i]}"
  done
  echo ""
  printf 'RUN AGAIN     %s\n' "$MD_MM_CMD"
  echo ""
  return 1
}

# --------------------------------------------------------------------------
# plumbing
# --------------------------------------------------------------------------
md_mm_py() {
  python3 "$MD_MM_LIB/migrate_machine.py" "$@"
}

md_mm_run_cli() {
  # Canonical CLI path — never a copy of its logic.
  bash "$MD_MM_REPO/deploy/manage_deploy.sh" "$@"
}

md_mm_env_value() {
  local file="$1" key="$2" default="${3:-}"
  [[ -f "$file" ]] || { echo "$default"; return 0; }
  python3 - "$file" "$key" "$default" <<'PY'
import sys
path, key, default = sys.argv[1], sys.argv[2], sys.argv[3]
val = default
with open(path, encoding="utf-8") as fh:
    for line in fh:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if k.strip() == key:
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            val = v
print(val)
PY
}

md_mm_init() {
  MD_MM_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  MD_MM_REPO="$(cd "$MD_MM_LIB/../.." && pwd)"
  # shellcheck source=deploy/lib/deploy_source.sh
  source "$MD_MM_LIB/deploy_source.sh"
  # shellcheck source=deploy/lib/confirmation.sh
  source "$MD_MM_LIB/confirmation.sh"
  # shellcheck source=deploy/lib/migrate_release.sh
  source "$MD_MM_LIB/migrate_release.sh"
  md_deploy_source_init

  MD_MM_PROJECT_ROOT="$MD_DEPLOY_PROJECT_ROOT"
  MD_MM_DIR="${MD_MM_DIR:-$MD_MM_PROJECT_ROOT/deployments/migration}"
  MD_MM_BUNDLE_DIR="$MD_MM_DIR/bundle"
  MD_MM_OUTBOX="$MD_MM_DIR/outbox"
  MD_MM_LIVE_ENV="$MD_MM_PROJECT_ROOT/.env"
  MD_MM_BUILD_INFO="$MD_MM_PROJECT_ROOT/.build-info.json"
  MD_MM_APP_BASE="${MD_MM_APP_BASE:-http://127.0.0.1:8000}"
  MD_MM_QDRANT_BASE="$(md_mm_env_value "$MD_MM_LIVE_ENV" QDRANT_URL "http://127.0.0.1:6333")"
  MD_MM_OLLAMA_BASE="$(md_mm_env_value "$MD_MM_LIVE_ENV" OLLAMA_BASE_URL "http://127.0.0.1:11434")"
  MD_MM_GOLDEN="$MD_MM_REPO/backend/tests/golden/queries.json"
  mkdir -p "$MD_MM_DIR" 2>/dev/null || true
}

# --------------------------------------------------------------------------
# role detection — observable state only, never an operator flag
# --------------------------------------------------------------------------
md_mm_has_live_corpus() {
  # PostgreSQL stays up during the freeze, so this survives a stopped backend.
  [[ -f "$MD_MM_BUILD_INFO" ]] || return 1
  md_migrate_release_load_database_url "$MD_MM_LIVE_ENV" >/dev/null 2>&1 || return 1
  local n
  n="$(md_mm_py db-facts --url "$MD_MIGRATE_RELEASE_DATABASE_URL" 2>/dev/null \
       | python3 -c 'import json,sys; print(json.load(sys.stdin).get("sources",0))' 2>/dev/null || echo 0)"
  [[ "${n:-0}" -gt 0 ]]
}

md_mm_has_bundle() {
  [[ -f "$MD_MM_BUNDLE_DIR/bundle-manifest.json" ]]
}

md_mm_detect_role() {
  # Recorded role always wins: this is what makes resume deterministic.
  if [[ -f "$MD_MM_DIR/state.json" ]]; then
    local role
    role="$(md_mm_py state-get --dir "$MD_MM_DIR" --key role)" || return 1
    if [[ "$role" == "source" || "$role" == "target" ]]; then
      MD_MM_ROLE="$role"
      return 0
    fi
  fi

  local live=0 bundle=0
  if md_mm_has_live_corpus; then live=1; fi
  if md_mm_has_bundle; then bundle=1; fi

  if [[ "$live" -eq 1 && "$bundle" -eq 1 ]]; then
    md_mm_fail MM-ROLE01 \
      "Host role is ambiguous." \
      "Both a live corpus and an incoming migration bundle were found. Acting on either assumption could freeze the wrong host or erase authoritative data." \
      "Do not continue. Confirm which host is authoritative and remove only the incorrect target artifact after review."
    return 1
  fi
  if [[ "$live" -eq 1 ]]; then MD_MM_ROLE="source"; return 0; fi
  if [[ "$bundle" -eq 1 ]]; then MD_MM_ROLE="target"; return 0; fi

  # No authoritative runtime and no bundle: a host that cannot be the source.
  if [[ ! -f "$MD_MM_BUILD_INFO" ]]; then MD_MM_ROLE="target"; return 0; fi

  md_mm_fail MM-ROLE02 \
    "Host role could not be determined." \
    "A deployed build was found but no live corpus and no migration bundle, so this host is neither clearly the source nor clearly the target." \
    "Review the host. If it is the intended target, remove the stale $MD_MM_BUILD_INFO after confirming no authoritative data is present."
  return 1
}

# --------------------------------------------------------------------------
# phase bookkeeping
# --------------------------------------------------------------------------
md_mm_phase_done() {
  local phase="$1"
  md_mm_py state-get --dir "$MD_MM_DIR" --key completed_phases 2>/dev/null \
    | grep -qx "$phase"
}

md_mm_phase_complete() {
  md_mm_py state-complete --dir "$MD_MM_DIR" --phase "$1"
}

md_mm_banner() {
  echo "=== machine migration ==="
  echo "  host         : $(hostname)"
  md_mm_py state-show --dir "$MD_MM_DIR" 2>/dev/null || true
  echo ""
}

md_mm_confirm_once() {
  # A destructive gate is never auto-repeated: the word is recorded in state.
  local word="$1" prompt="$2"
  if md_mm_py state-has-confirm --dir "$MD_MM_DIR" --word "$word" 2>/dev/null; then
    echo "  (${word} already confirmed for this migration)"
    return 0
  fi
  echo ""
  echo "$prompt"
  if ! md_confirm_typed "Type ${word} to continue:" "$word"; then
    md_mm_fail "MM-CONF-${word}" \
      "${word} confirmation was not given." \
      "This step is irreversible without rollback, so it never proceeds implicitly." \
      "Run the command again and type ${word} exactly when prompted."
    return 1
  fi
  md_mm_py state-confirm --dir "$MD_MM_DIR" --word "$word"
  return 0
}

# --------------------------------------------------------------------------
# fact collection
# --------------------------------------------------------------------------
md_mm_load_db_url() {
  md_migrate_release_load_database_url "$MD_MM_LIVE_ENV" || return 1
  MD_MM_MIGRATE_URL="$MD_MIGRATE_RELEASE_DATABASE_URL"
}

md_mm_collect_facts() {
  local out_dir="$1"
  mkdir -p "$out_dir"
  md_mm_py db-facts --url "$MD_MM_MIGRATE_URL" > "$out_dir/db-facts.json"
  md_mm_py qdrant-facts --base "$MD_MM_QDRANT_BASE" \
    --collections "${MD_MM_QDRANT_COLLECTIONS[@]}" > "$out_dir/qdrant-facts.json"
  md_mm_py ollama-facts --base "$MD_MM_OLLAMA_BASE" \
    --models "${MD_MM_MODELS[@]}" > "$out_dir/ollama-facts.json"
}

md_mm_json_get() {
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1]))
keys=sys.argv[2].split(".")
for k in keys:
    d = (d or {}).get(k) if isinstance(d, dict) else None
print("" if d is None else d)' "$1" "$2"
}

# --------------------------------------------------------------------------
# SOURCE phases
# --------------------------------------------------------------------------
md_mm_source_preflight() {
  echo "[source 1/5] preflight (read-only)"
  md_mm_pf_reset
  local repo="$MD_DEPLOY_REPO_ROOT"

  if deploy_guard_assert_not_detached "$repo" >/dev/null 2>&1 \
     && deploy_guard_assert_on_main_branch "$repo" >/dev/null 2>&1; then
    md_mm_pf_ok "on main branch"
  else
    md_mm_pf_add MM-SP01 "The repository is not on the main branch." \
      "deploy full and migrate release refuse any non-main or detached checkout, so the cutover would be refused later." \
      "git -C $repo checkout main"
  fi

  if deploy_guard_assert_clean_worktree "$repo" "operator checkout" >/dev/null 2>&1; then
    md_mm_pf_ok "working tree clean"
  else
    md_mm_pf_add MM-SP02 "The working tree has uncommitted changes." \
      "A release deploy is refused from a dirty tree, and a dirty tree makes the cutover commit unreproducible." \
      "Commit or stash the changes in $repo"
  fi

  deploy_guard_fetch_origin "$repo" >/dev/null 2>&1 || true
  if deploy_guard_assert_local_main_matches_origin "$repo" >/dev/null 2>&1; then
    MD_MM_CCUT="$(deploy_guard_origin_main_hash "$repo")"
    md_mm_pf_ok "main == origin/main (${MD_MM_CCUT:0:12})"
  else
    md_mm_pf_add MM-SP03 "Local main does not match origin/main." \
      "The target deploys the origin/main tip, so a diverged main means the target would not receive the commit this migration recorded." \
      "Push or reset main so it matches origin/main, then run the command again."
  fi

  if md_mm_load_db_url >/dev/null 2>&1; then
    md_mm_pf_ok "database reachable"
  else
    md_mm_pf_add MM-SP04 "The live database is not reachable." \
      "Counts, the Alembic revision, and the dump all come from this database." \
      "Check DATABASE_URL in $MD_MM_LIVE_ENV and that PostgreSQL is running."
  fi

  local target_host
  target_host="$(md_mm_env_value "$MD_MM_REPO/deploy/deploy.local.conf" MIGRATION_TARGET_HOST "")"
  if [[ -n "$target_host" ]]; then
    if ssh -o BatchMode=yes -o ConnectTimeout=10 "$target_host" true >/dev/null 2>&1; then
      md_mm_pf_ok "target reachable ($target_host)"
      MD_MM_TARGET_HOST="$target_host"
    else
      md_mm_pf_add MM-SP05 "The target host is not reachable without a password ($target_host)." \
        "The bundle is transferred non-interactively, so key-based access must already work." \
        "Install the source public key on the target, then verify: ssh $target_host true"
    fi
  else
    md_mm_pf_add MM-SP06 "MIGRATION_TARGET_HOST is not configured." \
      "The tool must know where to deliver the bundle, and guessing a production host is unsafe." \
      "Add MIGRATION_TARGET_HOST=user@host to $MD_MM_REPO/deploy/deploy.local.conf"
  fi

  local idx=""
  idx="$(curl -sf --max-time 10 "$MD_MM_APP_BASE/api/health" 2>/dev/null \
        | python3 -c 'import json,sys; print((json.load(sys.stdin) or {}).get("index_job_status",""))' 2>/dev/null || echo "")"
  if [[ "$idx" == "running" ]]; then
    md_mm_pf_add MM-SP07 "An indexing job is currently running." \
      "A dump taken while indexing writes would capture a corpus that does not match the Qdrant snapshot." \
      "Wait for indexing to finish, then run the command again."
  else
    md_mm_pf_ok "no indexing job running"
  fi

  md_mm_pf_report || return 1
  mkdir -p "$MD_MM_DIR"
  md_mm_collect_facts "$MD_MM_DIR/source-facts"
  {
    echo "{"
    echo "  \"host\": \"$(hostname)\","
    echo "  \"c_cut\": \"${MD_MM_CCUT:-}\","
    echo "  \"checked_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""
    echo "}"
  } > "$MD_MM_DIR/preflight-source.json"
  {
    echo "# Source preflight"
    echo ""
    echo "- host: $(hostname)"
    echo "- cutover commit: \`${MD_MM_CCUT:-}\`"
    echo "- result: PASS"
  } > "$MD_MM_DIR/preflight-source.md"
  md_mm_py state-set --dir "$MD_MM_DIR" \
    "c_cut=${MD_MM_CCUT:-}" "target_hostname=${MD_MM_TARGET_HOST:-}" \
    "source_hostname=$(hostname)"
  echo "  preflight: PASS"
  md_mm_phase_complete source_preflight
}

md_mm_source_baseline() {
  echo "[source 2/5] retrieval baseline (read-only, backend must be live)"
  # shellcheck source=scripts/lib/deploy-env.sh
  source "$MD_MM_REPO/scripts/lib/deploy-env.sh"
  if ! curl -sf --max-time 10 "$MD_MM_APP_BASE/api/health" >/dev/null 2>&1; then
    md_mm_fail MM-SB01 \
      "The backend is not answering, so the retrieval baseline cannot be captured." \
      "The baseline is the only evidence that the target retrieves the same results as this host; it must be taken before the freeze." \
      "Start the backend: sudo bash deploy/manage_deploy.sh restart backend"
    return 1
  fi
  if ! md_mm_py baseline-capture \
      --base "$MD_MM_APP_BASE" --user "$STAGING_ADMIN_USER" --password "$STAGING_ADMIN_PASSWORD" \
      --golden "$MD_MM_GOLDEN" --out "$MD_MM_DIR/retrieval-baseline.json"; then
    md_mm_fail MM-SB02 \
      "The retrieval baseline could not be captured." \
      "Either the admin credentials are wrong or the chat path is failing; without a baseline the target cannot prove retrieval parity." \
      "Verify STAGING_ADMIN_USER / STAGING_ADMIN_PASSWORD resolve correctly, then run the command again."
    return 1
  fi
  md_mm_phase_complete source_baseline
}

md_mm_source_freeze() {
  echo "[source 3/5] freeze"
  md_mm_confirm_once FREEZE \
"This stops the authoritative backend on $(hostname).
Writes to PostgreSQL and Qdrant become impossible while frozen.
Rollback before access is switched is: start the backend again (zero data loss)." || return 1

  md_mm_run_cli --action stop --module backend || true
  sleep 2
  if curl -sf --max-time 5 "$MD_MM_APP_BASE/api/health" >/dev/null 2>&1; then
    md_mm_fail MM-SF01 \
      "The backend is still answering after the stop request." \
      "A dump taken while the application can still write would not match the Qdrant snapshot." \
      "Stop it manually: sudo systemctl stop ai-agent-backend"
    return 1
  fi
  echo "  writes frozen"
  md_mm_phase_complete source_freeze
}

md_mm_source_capture() {
  echo "[source 4/5] capture"
  local mig_id
  mig_id="$(md_mm_py state-get --dir "$MD_MM_DIR" --key migration_id)"
  rm -rf "$MD_MM_OUTBOX"
  mkdir -p "$MD_MM_OUTBOX"

  md_mm_load_db_url || return 1

  # Reuse the production backup command; never a private pg_dump.
  if ! md_mm_run_cli backup db; then
    md_mm_fail MM-SC01 \
      "backup db failed, so no dump exists to migrate." \
      "The dump is the only copy of the database that travels to the target." \
      "Check free disk space and PostgreSQL access, then run the command again."
    return 1
  fi
  local dump
  dump="$(ls -1t "$MD_MM_PROJECT_ROOT/backups/"*.dump 2>/dev/null | head -1 || echo "")"
  if [[ -z "$dump" ]]; then
    md_mm_fail MM-SC02 \
      "No dump file was found after backup db reported success." \
      "The bundle cannot be built without the dump." \
      "Inspect $MD_MM_PROJECT_ROOT/backups and run the command again."
    return 1
  fi
  cp "$dump" "$MD_MM_OUTBOX/"

  local snap_args=()
  local coll
  for coll in "${MD_MM_QDRANT_COLLECTIONS[@]}"; do
    [[ "$coll" == "site_knowledge" ]] || continue
    local snap_name
    snap_name="$(curl -sf -X POST "$MD_MM_QDRANT_BASE/collections/$coll/snapshots" \
      | python3 -c 'import json,sys; print((json.load(sys.stdin).get("result") or {}).get("name",""))' 2>/dev/null || echo "")"
    if [[ -z "$snap_name" ]]; then
      md_mm_fail MM-SC03 \
        "Qdrant did not create a snapshot for collection $coll." \
        "The vectors must travel as a native snapshot; a filesystem copy is not consistent and re-indexing changes retrieval." \
        "Confirm Qdrant is running at $MD_MM_QDRANT_BASE, then run the command again."
      return 1
    fi
    if ! curl -sf -o "$MD_MM_OUTBOX/$snap_name" \
        "$MD_MM_QDRANT_BASE/collections/$coll/snapshots/$snap_name"; then
      md_mm_fail MM-SC04 \
        "The Qdrant snapshot for $coll could not be downloaded." \
        "The bundle must physically contain the snapshot." \
        "Check disk space in $MD_MM_OUTBOX, then run the command again."
      return 1
    fi
    snap_args+=(--snapshot "$coll=$MD_MM_OUTBOX/$snap_name")
  done

  md_mm_collect_facts "$MD_MM_OUTBOX/facts"
  cp "$MD_MM_DIR/retrieval-baseline.json" "$MD_MM_OUTBOX/retrieval-baseline.json"

  local release ccut
  release="$(md_mm_json_get "$MD_MM_BUILD_INFO" release)"
  ccut="$(md_mm_py state-get --dir "$MD_MM_DIR" --key c_cut)"

  md_mm_py bundle-manifest \
    --migration-id "$mig_id" \
    --source-hostname "$(hostname)" \
    --operator "${SUDO_USER:-${USER:-unknown}}" \
    --release "$release" \
    --c-cut "$ccut" \
    --db-facts "$MD_MM_OUTBOX/facts/db-facts.json" \
    --qdrant-facts "$MD_MM_OUTBOX/facts/qdrant-facts.json" \
    --ollama-facts "$MD_MM_OUTBOX/facts/ollama-facts.json" \
    --dump "$MD_MM_OUTBOX/$(basename "$dump")" \
    --baseline "$MD_MM_OUTBOX/retrieval-baseline.json" \
    --out-json "$MD_MM_OUTBOX/bundle-manifest.json" \
    --out-md "$MD_MM_OUTBOX/bundle-manifest.md" \
    "${snap_args[@]}" || return 1

  md_mm_py bundle-verify --bundle "$MD_MM_OUTBOX" \
    --manifest "$MD_MM_OUTBOX/bundle-manifest.json" --migration-id "$mig_id" || {
    md_mm_fail MM-SC05 \
      "The freshly created bundle failed its own integrity check." \
      "A bundle that cannot verify locally must never be shipped to the target." \
      "Remove $MD_MM_OUTBOX and run the command again."
    return 1
  }
  md_mm_py state-set --dir "$MD_MM_DIR" "bundle_id=$mig_id"
  md_mm_phase_complete source_capture
}

md_mm_source_send() {
  echo "[source 5/5] deliver bundle"
  local target
  target="$(md_mm_py state-get --dir "$MD_MM_DIR" --key target_hostname)"
  if [[ -z "$target" ]]; then
    md_mm_fail MM-SS01 \
      "No target host is recorded for this migration." \
      "The bundle cannot be delivered without a destination." \
      "Add MIGRATION_TARGET_HOST=user@host to deploy/deploy.local.conf and run the command again."
    return 1
  fi
  local remote="${MD_MM_REMOTE_DIR:-/opt/ai-site-agent/deployments/migration/bundle}"
  ssh -o BatchMode=yes "$target" "mkdir -p '$remote'" || {
    md_mm_fail MM-SS02 \
      "The bundle directory could not be created on $target." \
      "Without it the bundle cannot be delivered." \
      "Check that the SSH user can write $remote on the target."
    return 1
  }
  if ! scp -q "$MD_MM_OUTBOX"/* "$target:$remote/"; then
    md_mm_fail MM-SS03 \
      "The bundle transfer to $target failed." \
      "A partial transfer must never be restored from." \
      "Fix connectivity or disk space on the target, then run the command again."
    return 1
  fi
  # Re-verify every checksum on the far side before declaring delivery.
  local py_remote="$remote/migrate_machine.py"
  scp -q "$MD_MM_LIB/migrate_machine.py" "$target:$py_remote"
  if ! ssh -o BatchMode=yes "$target" \
      "python3 '$py_remote' bundle-verify --bundle '$remote' --manifest '$remote/bundle-manifest.json'"; then
    md_mm_fail MM-SS04 \
      "The delivered bundle did not verify on $target." \
      "The bytes that arrived differ from the bytes that were captured." \
      "Delete $remote on the target, then run the command again to re-deliver."
    return 1
  fi
  md_mm_phase_complete source_send
  echo ""
  echo "BUNDLE DELIVERED"
  echo "Next action: run the same command on the TARGET host."
  echo "  $MD_MM_CMD"
  echo ""
  echo "This host stays frozen. Rollback before access is switched is:"
  echo "  sudo systemctl start ai-agent-backend"
}

# --------------------------------------------------------------------------
# TARGET phases
# --------------------------------------------------------------------------
md_mm_target_preflight() {
  echo "[target 1/12] preflight (read-only)"
  md_mm_pf_reset

  local locale_ok
  locale_ok="$(locale 2>/dev/null | grep -c 'C.UTF-8\|C\.utf8' || true)"
  if [[ "${locale_ok:-0}" -gt 0 ]]; then
    md_mm_pf_ok "locale is C.UTF-8"
  else
    md_mm_pf_add MM-TP01 "The system locale is not C.UTF-8." \
      "PostgreSQL fixes collation at initdb time; a different collation silently changes text ordering and comparison after restore." \
      "sudo update-locale LANG=C.UTF-8 and recreate the cluster before restoring."
  fi

  local pyver
  pyver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "")"
  if [[ "$pyver" == "3.12" ]]; then
    md_mm_pf_ok "python $pyver"
  else
    md_mm_pf_add MM-TP02 "python3 is ${pyver:-missing}, not 3.12." \
      "The backend virtualenv and pinned wheels are built for 3.12." \
      "sudo apt install python3.12"
  fi

  if command -v psql >/dev/null 2>&1; then
    md_mm_pf_ok "psql present"
  else
    md_mm_pf_add MM-TP03 "psql is not installed." \
      "The restore and every database comparison use psql." \
      "sudo apt install postgresql-client-16"
  fi

  if command -v pg_restore >/dev/null 2>&1; then
    md_mm_pf_ok "pg_restore present"
  else
    md_mm_pf_add MM-TP04 "pg_restore is not installed." \
      "The database cannot be restored without it." \
      "sudo apt install postgresql-client-16"
  fi

  if [[ -f "$MD_MM_LIVE_ENV" ]]; then
    local mode
    mode="$(stat -c '%a' "$MD_MM_LIVE_ENV" 2>/dev/null || echo "")"
    if [[ "$mode" == "600" ]]; then
      md_mm_pf_ok ".env present, mode 600"
    else
      md_mm_pf_add MM-TP05 "$MD_MM_LIVE_ENV has mode ${mode:-unknown}, not 600." \
        "It holds the database password and admin credentials." \
        "sudo chmod 600 $MD_MM_LIVE_ENV"
    fi
  else
    md_mm_pf_add MM-TP06 "$MD_MM_LIVE_ENV does not exist." \
      "The runtime configuration and DATABASE_URL must exist before anything is restored or deployed." \
      "Create it from .env.example with rotated secrets, then chmod 600."
  fi

  # The rehearsal deploy runs migrations, so the database must already exist.
  # Catch it here with the exact fix rather than inside a failing deploy.
  if [[ -f "$MD_MM_LIVE_ENV" ]] && md_mm_load_db_url >/dev/null 2>&1; then
    if md_mm_py db-ping --url "$MD_MM_MIGRATE_URL" >/dev/null 2>&1; then
      md_mm_pf_ok "database reachable"
    else
      local dbn
      dbn="$(md_migrate_release_db_name "$MD_MM_MIGRATE_URL")"
      md_mm_pf_add MM-TP11 "The database '$dbn' cannot be reached." \
        "The rehearsal deploy runs Alembic against it, and the restore later replaces it; both need it to exist with the right owner and collation." \
        "sudo -u postgres createdb -O ai_agent -E UTF8 --lc-collate=C.UTF-8 --lc-ctype=C.UTF-8 -T template0 $dbn"
    fi
  fi

  if curl -sf --max-time 10 "$MD_MM_QDRANT_BASE" >/dev/null 2>&1; then
    md_mm_pf_ok "qdrant reachable"
  else
    md_mm_pf_add MM-TP07 "Qdrant is not reachable at $MD_MM_QDRANT_BASE." \
      "The vector snapshot is restored through its API." \
      "sudo systemctl start qdrant"
  fi

  if curl -sf --max-time 10 "$MD_MM_OLLAMA_BASE/api/version" >/dev/null 2>&1; then
    md_mm_pf_ok "ollama reachable"
  else
    md_mm_pf_add MM-TP08 "Ollama is not reachable at $MD_MM_OLLAMA_BASE." \
      "Embeddings are produced by Ollama; retrieval cannot be validated without it." \
      "sudo systemctl start ollama"
  fi

  local repo="$MD_DEPLOY_REPO_ROOT"
  if git -C "$repo" ls-remote --exit-code origin >/dev/null 2>&1; then
    md_mm_pf_ok "git remote reachable non-interactively"
  else
    md_mm_pf_add MM-TP09 "git cannot reach origin without prompting." \
      "deploy full fetches origin/main; an interactive prompt would stall the cutover." \
      "Install an SSH deploy key and verify: git -C $repo fetch"
  fi

  local free_kb
  free_kb="$(df -Pk "$MD_MM_PROJECT_ROOT" 2>/dev/null | awk 'NR==2{print $4}' || echo 0)"
  if [[ "${free_kb:-0}" -gt 10485760 ]]; then
    md_mm_pf_ok "disk headroom $((free_kb / 1024 / 1024)) GiB"
  else
    md_mm_pf_add MM-TP10 "Less than 10 GiB is free on $MD_MM_PROJECT_ROOT." \
      "A restore or deploy that runs out of space leaves a partially written state." \
      "Free disk space, then run the command again."
  fi

  md_mm_pf_report || return 1
  {
    echo "{ \"host\": \"$(hostname)\", \"result\": \"PASS\","
    echo "  \"checked_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" }"
  } > "$MD_MM_DIR/preflight-target.json"
  { echo "# Target preflight"; echo ""; echo "- host: $(hostname)"; echo "- result: PASS"; } \
    > "$MD_MM_DIR/preflight-target.md"
  echo "  preflight: PASS"
  md_mm_phase_complete target_preflight
}

md_mm_target_rehearse() {
  echo "[target 2/12] rehearse the existing deploy path"
  echo "  This warms the virtualenv, node_modules and dashboard build so the"
  echo "  cutover deploy is incremental, and proves the deploy path before the window."
  if ! md_mm_run_cli deploy full; then
    md_mm_fail MM-TR01 \
      "The rehearsal deploy failed." \
      "This is the same deploy that runs during the cutover. Failing now is free; failing inside the downtime window is not." \
      "Read the deploy output above, fix the cause, then run the command again."
    return 1
  fi
  md_mm_phase_complete target_rehearse
}

md_mm_target_bundle() {
  echo "[target 3/12] verify bundle"
  if ! md_mm_has_bundle; then
    # End of run 1: the host is prepared and there is nothing left to do here
    # until the source has produced a bundle.
    echo ""
    echo "TARGET READY"
    echo "Next action: run the same command on the SOURCE host."
    echo "  $MD_MM_CMD"
    return 10
  fi
  if ! md_mm_py bundle-verify --bundle "$MD_MM_BUNDLE_DIR" \
      --manifest "$MD_MM_BUNDLE_DIR/bundle-manifest.json"; then
    md_mm_fail MM-TB01 \
      "The migration bundle failed integrity verification." \
      "A dump or snapshot does not match the checksum recorded when it was captured, so it may be truncated, stale, or from another migration." \
      "Delete $MD_MM_BUNDLE_DIR and re-run the command on the SOURCE host to deliver a fresh bundle."
    return 1
  fi
  local mig_id src_host
  mig_id="$(md_mm_json_get "$MD_MM_BUNDLE_DIR/bundle-manifest.json" migration_id)"
  src_host="$(md_mm_json_get "$MD_MM_BUNDLE_DIR/bundle-manifest.json" source_hostname)"
  md_mm_py state-set --dir "$MD_MM_DIR" \
    "bundle_id=$mig_id" \
    "c_cut=$(md_mm_json_get "$MD_MM_BUNDLE_DIR/bundle-manifest.json" c_cut)" \
    "source_hostname=$src_host" \
    "target_hostname=$(hostname)"
  md_mm_phase_complete target_bundle
}

md_mm_target_restore() {
  echo "[target 4/12] restore PostgreSQL and Qdrant"
  local manifest="$MD_MM_BUNDLE_DIR/bundle-manifest.json"
  local db_name dump_name
  db_name="$(md_mm_json_get "$manifest" database_name)"
  dump_name="$(md_mm_json_get "$manifest" dump.filename)"

  # Verify integrity immediately before destructive work, not just on arrival.
  md_mm_py bundle-verify --bundle "$MD_MM_BUNDLE_DIR" --manifest "$manifest" || {
    md_mm_fail MM-TX01 \
      "The bundle no longer matches its checksums." \
      "Nothing is erased unless the replacement data is provably intact." \
      "Re-deliver the bundle from the source host."
    return 1
  }

  md_mm_confirm_once ERASE \
"This drops and recreates the database '$db_name' on $(hostname)
and replaces the Qdrant collection site_knowledge.
The verified bundle ($dump_name) becomes the only source of data.
The source host is untouched and remains the rollback path." || return 1

  md_mm_load_db_url || return 1
  local conn_json
  conn_json="$(python3 -c '
import json, sys
sys.path.insert(0, sys.argv[2])
from migrate_machine import parse_db_url
print(json.dumps(parse_db_url(sys.argv[1])))' "$MD_MM_MIGRATE_URL" "$MD_MM_LIB")"
  local pg_host pg_port pg_user pg_pass
  pg_host="$(echo "$conn_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["host"])')"
  pg_port="$(echo "$conn_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["port"])')"
  pg_user="$(echo "$conn_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["user"])')"
  pg_pass="$(echo "$conn_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["password"])')"

  if [[ "$db_name" == *recovery* ]]; then
    md_mm_fail MM-TX02 \
      "The restore target database name contains 'recovery' ($db_name)." \
      "The recovery database is never a migration target; restoring into it would leave the real database empty." \
      "Correct DATABASE_URL in $MD_MM_LIVE_ENV and run the command again."
    return 1
  fi

  # The dump path is derived from the verified manifest, never typed.
  local dump_path="$MD_MM_BUNDLE_DIR/$dump_name"
  echo "  restoring $dump_name → $db_name"
  if ! PGPASSWORD="$pg_pass" dropdb --if-exists -h "$pg_host" -p "$pg_port" -U "$pg_user" "$db_name" \
     || ! PGPASSWORD="$pg_pass" createdb -h "$pg_host" -p "$pg_port" -U "$pg_user" \
          -O "$pg_user" -E UTF8 --lc-collate=C.UTF-8 --lc-ctype=C.UTF-8 -T template0 "$db_name"; then
    md_mm_fail MM-TX03 \
      "The target database could not be recreated." \
      "A restore into an existing schema would collide, so the database is always recreated first." \
      "Check that $pg_user may drop and create databases, then run the command again."
    return 1
  fi
  if ! PGPASSWORD="$pg_pass" pg_restore --exit-on-error --single-transaction \
      -h "$pg_host" -p "$pg_port" -U "$pg_user" -d "$db_name" "$dump_path"; then
    md_mm_fail MM-TX04 \
      "pg_restore failed, so the database is empty rather than partially restored." \
      "The restore runs in a single transaction with --exit-on-error precisely so a failure cannot leave half the data behind." \
      "Read the pg_restore error above, resolve it, then run the command again."
    return 1
  fi
  echo "  PostgreSQL restored"

  local snap
  snap="$(python3 -c '
import json, sys
m = json.load(open(sys.argv[1]))
for s in m.get("qdrant_snapshots", []):
    if s["collection"] == "site_knowledge":
        print(s["filename"]); break' "$manifest")"
  if [[ -z "$snap" ]]; then
    md_mm_fail MM-TX05 \
      "The bundle contains no site_knowledge snapshot." \
      "Vectors are never rebuilt as part of a migration: re-indexing changes retrieval results." \
      "Re-run the command on the source host to capture a complete bundle."
    return 1
  fi
  curl -sf -X DELETE "$MD_MM_QDRANT_BASE/collections/site_knowledge" >/dev/null 2>&1 || true
  if ! curl -sf -X POST -H 'Content-Type:multipart/form-data' \
      -F "snapshot=@$MD_MM_BUNDLE_DIR/$snap" \
      "$MD_MM_QDRANT_BASE/collections/site_knowledge/snapshots/upload?priority=snapshot" >/dev/null; then
    md_mm_fail MM-TX06 \
      "The Qdrant snapshot restore failed." \
      "Retrieval requires the original vectors; clearing the collection or re-indexing is not an acceptable substitute." \
      "Confirm Qdrant is running at $MD_MM_QDRANT_BASE with enough disk, then run the command again."
    return 1
  fi
  echo "  Qdrant site_knowledge restored"

  # Answer cache is deliberately recreated empty with identical vector params.
  local vsize vdist
  vsize="$(md_mm_json_get "$manifest" qdrant.vector_size)"
  vdist="$(md_mm_json_get "$manifest" qdrant.distance)"
  curl -sf -X PUT -H 'Content-Type: application/json' \
    -d "{\"vectors\":{\"size\":$vsize,\"distance\":\"$vdist\"}}" \
    "$MD_MM_QDRANT_BASE/collections/site_knowledge_answer_cache" >/dev/null 2>&1 || true
  echo "  answer cache recreated empty ($vsize/$vdist)"

  {
    echo "{"
    echo "  \"migration_id\": \"$(md_mm_json_get "$manifest" migration_id)\","
    echo "  \"restored_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"database\": \"$db_name\","
    echo "  \"dump\": \"$dump_name\","
    echo "  \"qdrant_snapshot\": \"$snap\","
    echo "  \"answer_cache\": \"recreate-empty\","
    echo "  \"result\": \"PASS\""
    echo "}"
  } > "$MD_MM_DIR/restore-report.json"
  {
    echo "# Restore report"
    echo ""
    echo "- migration id: \`$(md_mm_json_get "$manifest" migration_id)\`"
    echo "- restored at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- database: \`$db_name\`"
    echo "- dump: \`$dump_name\`"
    echo "- qdrant snapshot: \`$snap\`"
    echo "- answer cache: recreated empty"
    echo "- result: PASS"
  } > "$MD_MM_DIR/restore-report.md"

  md_mm_phase_complete target_restore
}

md_mm_target_gate() {
  echo "[target 5/12] verify restored data against the bundle"
  md_mm_load_db_url || return 1
  md_mm_collect_facts "$MD_MM_DIR/target-facts"
  local manifest="$MD_MM_BUNDLE_DIR/bundle-manifest.json"

  local exp act
  for key in alembic_revision; do
    exp="$(md_mm_json_get "$manifest" "$key")"
    act="$(md_mm_json_get "$MD_MM_DIR/target-facts/db-facts.json" "$key")"
    if [[ "$exp" != "$act" ]]; then
      md_mm_fail MM-TG01 \
        "The restored Alembic revision is '$act' but the bundle recorded '$exp'." \
        "A different revision means the restored schema is not the schema that was captured." \
        "Re-deliver the bundle from the source host and restore again."
      return 1
    fi
  done

  local ekeys=(sources chunks chat_messages answer_traces)
  for key in "${ekeys[@]}"; do
    exp="$(md_mm_json_get "$manifest" "counts.$key")"
    act="$(md_mm_json_get "$MD_MM_DIR/target-facts/db-facts.json" "$key")"
    if [[ "$exp" != "$act" ]]; then
      md_mm_fail MM-TG02 \
        "Restored $key is $act but the bundle recorded $exp." \
        "The restore did not reproduce the captured database exactly, so this is not the same corpus." \
        "Re-deliver the bundle from the source host and restore again."
      return 1
    fi
  done

  exp="$(md_mm_json_get "$manifest" qdrant.points)"
  act="$(md_mm_json_get "$MD_MM_DIR/target-facts/qdrant-facts.json" site_knowledge.points)"
  if [[ "$exp" != "$act" ]]; then
    md_mm_fail MM-TG03 \
      "Qdrant holds $act points but the bundle recorded $exp." \
      "A partial vector restore degrades retrieval silently, without any runtime error." \
      "Re-run the command to restore the snapshot again; never clear the collection or re-index as a fix."
    return 1
  fi

  local mdig adig
  mdig="$(md_mm_json_get "$manifest" models.digests.bge-m3)"
  adig="$(md_mm_json_get "$MD_MM_DIR/target-facts/ollama-facts.json" digests.bge-m3)"
  if [[ -n "$mdig" && "$mdig" != "$adig" ]]; then
    md_mm_fail MM-TG04 \
      "The bge-m3 model digest does not match the source host." \
      "The stored vectors were produced by the source model. A different build embeds queries differently, so every answer degrades quietly with no error anywhere." \
      "Pull the exact model recorded in the bundle, or copy the model blob from the source host, then run the command again."
    return 1
  fi
  echo "  restored state matches the bundle"
  md_mm_phase_complete target_gate
}

md_mm_target_schema() {
  echo "[target 6/12] schema check"
  local restored repo_head
  restored="$(md_mm_json_get "$MD_MM_DIR/target-facts/db-facts.json" alembic_revision)"
  repo_head="$(md_migrate_release_heads "$MD_DEPLOY_REPO_ROOT/backend" | head -1)"
  if [[ -n "$repo_head" && "$repo_head" != "$restored" ]]; then
    echo "  repository head ($repo_head) is ahead of restored ($restored) — running migrate release"
    if ! md_mm_run_cli migrate release --yes; then
      md_mm_fail MM-TS01 \
        "migrate release failed against the restored database." \
        "The deployed code expects a newer schema than the restored dump provides, and that gap must close before the application starts." \
        "Read the migrate release report above, resolve the cause, then run the command again."
      return 1
    fi
    # Acceptance reads target-facts; refresh after a schema advance so the
    # report reflects the post-migrate revision, not the restored dump.
    md_mm_load_db_url || return 1
    md_mm_py db-facts --url "$MD_MM_MIGRATE_URL" > "$MD_MM_DIR/target-facts/db-facts.json"
  else
    echo "  restored revision already matches the repository head — nothing to apply"
  fi
  md_mm_phase_complete target_schema
}

md_mm_target_deploy() {
  echo "[target 7/12] deploy"
  local repo="$MD_DEPLOY_REPO_ROOT" ccut origin_main
  ccut="$(md_mm_py state-get --dir "$MD_MM_DIR" --key c_cut)"
  deploy_guard_fetch_origin "$repo" >/dev/null 2>&1 || true
  origin_main="$(deploy_guard_origin_main_hash "$repo")"
  if [[ -n "$ccut" && "$ccut" != "$origin_main" ]]; then
    md_mm_fail MM-TD01 \
      "origin/main has moved since the bundle was captured." \
      "The bundle recorded ${ccut:0:12} but origin/main is now ${origin_main:0:12}. deploy full always deploys the origin/main tip, so the target would run code this migration never validated." \
      "Either restore origin/main to ${ccut:0:12}, or re-capture the bundle on the source host against the new tip."
    return 1
  fi
  if ! md_mm_run_cli deploy full; then
    md_mm_fail MM-TD02 \
      "deploy full failed on the target." \
      "The restored data is intact, but the application code is not in a serving state." \
      "Read the deploy output above, fix the cause, then run the command again."
    return 1
  fi
  md_mm_phase_complete target_deploy
}

md_mm_target_validate() {
  echo "[target 8/12] validate with the existing commands"
  MD_MM_HEALTH=fail MD_MM_SMOKE=fail MD_MM_VERIFY=fail
  md_mm_run_cli health >"$MD_MM_DIR/health.out" 2>&1 && MD_MM_HEALTH=pass || true
  SMOKE_CHAT=1 md_mm_run_cli smoke >"$MD_MM_DIR/smoke.out" 2>&1 && MD_MM_SMOKE=pass || true
  md_mm_run_cli verify-release >"$MD_MM_DIR/verify-release.out" 2>&1 && MD_MM_VERIFY=pass || true
  echo "  health=$MD_MM_HEALTH smoke=$MD_MM_SMOKE verify-release=$MD_MM_VERIFY"
  md_mm_py state-set --dir "$MD_MM_DIR" \
    "health=$MD_MM_HEALTH" "smoke=$MD_MM_SMOKE" "verify_release=$MD_MM_VERIFY"
  md_mm_phase_complete target_validate
}

md_mm_target_parity() {
  echo "[target 9/12] retrieval parity"
  # shellcheck source=scripts/lib/deploy-env.sh
  source "$MD_MM_REPO/scripts/lib/deploy-env.sh"
  if ! md_mm_py baseline-capture \
      --base "$MD_MM_APP_BASE" --user "$STAGING_ADMIN_USER" --password "$STAGING_ADMIN_PASSWORD" \
      --golden "$MD_MM_GOLDEN" --out "$MD_MM_DIR/retrieval-actual.json"; then
    md_mm_fail MM-TQ01 \
      "The retrieval replay could not run on the target." \
      "Without it there is no evidence that the migrated system retrieves the same results as the source." \
      "Confirm the backend answers and the admin credentials resolve, then run the command again."
    return 1
  fi
  md_mm_py baseline-compare \
    --baseline "$MD_MM_BUNDLE_DIR/retrieval-baseline.json" \
    --actual "$MD_MM_DIR/retrieval-actual.json" \
    --out "$MD_MM_DIR/retrieval-parity.json" || true
  md_mm_phase_complete target_parity
}

md_mm_target_report() {
  echo "[target 10/12] acceptance"
  local actual="$MD_MM_DIR/actual-state.json"
  python3 - "$MD_MM_DIR" "$MD_MM_BUILD_INFO" > "$actual" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else (default or {})
state = load(d / "state.json")
build = load(sys.argv[2])
print(json.dumps({
    "db": load(d / "target-facts" / "db-facts.json"),
    "qdrant": load(d / "target-facts" / "qdrant-facts.json"),
    "ollama": load(d / "target-facts" / "ollama-facts.json"),
    "deployed_commit": build.get("git_commit", ""),
    "release": build.get("release", ""),
    "health": state.get("health", ""),
    "smoke": state.get("smoke", ""),
    "verify_release": state.get("verify_release", ""),
}, indent=2))
PY
  local rc=0
  md_mm_py accept-report \
    --manifest "$MD_MM_BUNDLE_DIR/bundle-manifest.json" \
    --actual "$actual" \
    --parity "$MD_MM_DIR/retrieval-parity.json" \
    --out-json "$MD_MM_DIR/acceptance-report.json" \
    --out-md "$MD_MM_DIR/acceptance-report.md" || rc=$?
  if [[ "$rc" -ne 0 ]]; then
    md_mm_py state-set --dir "$MD_MM_DIR" "rollback_available=yes" "last_error_code=MM-TA01"
    echo ""
    echo "MIGRATION STOPPED"
    echo ""
    printf 'WHAT FAILED   %s\n' "One or more acceptance criteria did not match the source bundle."
    printf 'WHY           %s\n' "Acceptance is machine-to-machine. A mismatch means the target does not reproduce the source, so it must not take authority."
    printf 'HOW TO FIX    %s\n' "Read $MD_MM_DIR/acceptance-report.md. Rollback is available and loses nothing: this host has served no traffic."
    printf 'RUN AGAIN     %s\n' "$MD_MM_CMD"
    echo ""
    return 1
  fi
  md_mm_phase_complete target_report
}

md_mm_target_accept() {
  echo "[target 11/12] human acceptance"
  md_mm_confirm_once ACCEPT \
"Every automated criterion passed. See $MD_MM_DIR/acceptance-report.md
The tool does not accept a migration on its own." || return 1
  md_mm_phase_complete target_accept
}

md_mm_target_switch() {
  echo "[target 12/12] switch authority"
  md_mm_confirm_once SWITCH \
"This authorizes moving access to this host and starts the rollback window.
After this point, writes accepted here are discarded by a rollback —
there is no merge path between the two hosts." || return 1
  md_mm_phase_complete target_switch
  echo ""
  echo "MIGRATION COMPLETE"
  echo "  acceptance report: $MD_MM_DIR/acceptance-report.md"
  echo "  keep the source host frozen and intact until acceptance + 14 days"
}

# --------------------------------------------------------------------------
# rollback — decision human, execution automated, same one command
# --------------------------------------------------------------------------
md_mm_rollback() {
  echo "=== rollback: return authority to the source host ==="
  local source_host
  source_host="$(md_mm_py state-get --dir "$MD_MM_DIR" --key source_hostname)"
  md_mm_confirm_once ROLLBACK \
"This stops the target backend and returns authority to the source host.
Any writes this target accepted are DISCARDED — there is no merge path.
The source data is never modified by a rollback." || return 1

  md_mm_run_cli --action stop --module backend || true
  echo "  target backend stopped; target cannot accept writes"

  if [[ -n "$source_host" ]]; then
    echo ""
    echo "Run on the source host ($source_host) to resume service:"
    echo "  sudo systemctl start ai-agent-backend"
    echo "  bash deploy/manage_deploy.sh health"
    echo ""
    echo "Expected on the source host: health ok, its original Alembic revision"
    echo "and counts unchanged. A verify-release identity mismatch against a newer"
    echo "origin/main is expected drift, NOT a rollback failure — do not deploy to 'fix' it."
  fi
  {
    echo "{ \"rolled_back_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"target_host\": \"$(hostname)\", \"source_host\": \"$source_host\","
    echo "  \"target_writes_discarded\": true }"
  } > "$MD_MM_DIR/rollback-report.json"
  {
    echo "# Rollback report"
    echo ""
    echo "- rolled back at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- target host (stopped): $(hostname)"
    echo "- source host (authoritative): $source_host"
    echo "- writes accepted by the target: discarded, no merge path"
    echo "- source data modified: no"
  } > "$MD_MM_DIR/rollback-report.md"
  echo "  report: $MD_MM_DIR/rollback-report.md"
  md_mm_phase_complete rollback
}

# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
md_mm_run_phases() {
  local phase
  for phase in "$@"; do
    if md_mm_phase_done "$phase"; then
      echo "  (already done: $phase)"
      continue
    fi
    local rc=0
    "md_mm_$phase" || rc=$?
    if [[ "$rc" -eq 10 ]]; then
      return 0   # clean stop: operator must act on the other host
    fi
    [[ "$rc" -eq 0 ]] || return "$rc"
  done
}

md_migrate_machine() {
  if [[ $# -gt 0 ]]; then
    md_mm_fail MM-ARG01 \
      "migrate-machine does not take arguments (got '$1')." \
      "The tool determines the host role and the next phase from observable state; an operator-supplied phase or role could act on the wrong host." \
      "Run it with no arguments."
    return 1
  fi
  md_mm_init
  md_mm_detect_role || return 1

  local mig_id
  if [[ -f "$MD_MM_DIR/state.json" ]]; then
    mig_id="$(md_mm_py state-get --dir "$MD_MM_DIR" --key migration_id)"
  else
    mig_id="$(date -u +%Y%m%dT%H%M%SZ)-$(hostname -s 2>/dev/null || echo host)"
    md_mm_py state-init --dir "$MD_MM_DIR" --role "$MD_MM_ROLE" --migration-id "$mig_id" >/dev/null
  fi
  md_mm_banner

  if [[ "$MD_MM_ROLE" == "source" ]]; then
    md_mm_run_phases source_preflight source_baseline source_freeze source_capture source_send
    return $?
  fi

  # Rollback becomes reachable through the same command once acceptance failed.
  local rollback_available
  rollback_available="$(md_mm_py state-get --dir "$MD_MM_DIR" --key rollback_available --optional 2>/dev/null || echo "")"
  if [[ "$rollback_available" == "yes" ]] && ! md_mm_phase_done target_accept; then
    echo "A previous run stopped with failed acceptance criteria."
    echo "Report: $MD_MM_DIR/acceptance-report.md"
    echo ""
    if md_confirm "Roll back to the source host now?" "n"; then
      md_mm_rollback
      return $?
    fi
    echo "Continuing verification instead of rolling back."
    md_mm_py state-set --dir "$MD_MM_DIR" "rollback_available=no"
  fi

  md_mm_run_phases \
    target_preflight target_rehearse target_bundle target_restore target_gate \
    target_schema target_deploy target_validate target_parity target_report \
    target_accept target_switch
}
