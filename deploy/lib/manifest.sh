#!/usr/bin/env bash
# Deployment report (One Command Deployment) — SUCCESS and FAILED share one schema.
set -euo pipefail

# md_rollback_recommendation <failed_stage> <outcome>
md_rollback_recommendation() {
  local failed_stage="${1:-}"
  local outcome="${2:-failed}"
  if [[ "$outcome" == "success" ]]; then
    echo "none"
    return 0
  fi
  case "$failed_stage" in
    preflight|backup|migration_decision|build)
      echo "none_pre_sync"
      ;;
    schema_first)
      echo "review_schema_no_autodowngrade"
      ;;
    sync|post_sync_migrate|restart|health|verify_release|smoke|report)
      echo "redeploy_known_good_tip"
      ;;
    *)
      echo "redeploy_known_good_tip"
      ;;
  esac
}

# md_write_deploy_report — writes deployments/<ts>-<short>.json and updates latest.json
# Uses MD_REPORT_* environment variables (see deploy_source.sh).
md_write_deploy_report() {
  local project_root="${1:-${MD_DEPLOY_PROJECT_ROOT:-/opt/ai-site-agent}}"
  local deploy_dir="$project_root/deployments"
  local operator ts short commit release
  operator="${SUDO_USER:-${USER:-unknown}}"
  ts="$(date -u +%Y%m%d_%H%M%S)"
  commit="${MD_REPORT_DEPLOYED_COMMIT:-}"
  short="${MD_REPORT_DEPLOYED_COMMIT_SHORT:-}"
  if [[ -z "$short" && -n "$commit" && "$commit" != "unknown" ]]; then
    short="${commit:0:7}"
  fi
  short="${short:-unknown}"
  release="${MD_REPORT_DEPLOYED_RELEASE:-unknown}"

  local outcome="${MD_REPORT_OUTCOME:-failed}"
  local previous_commit="${MD_REPORT_PREVIOUS_COMMIT:-unknown}"
  local previous_release="${MD_REPORT_PREVIOUS_RELEASE:-unknown}"
  local origin_main="${MD_REPORT_ORIGIN_MAIN_COMMIT:-$commit}"
  local backup_id="${MD_REPORT_BACKUP_ID:-}"
  local backup_path="${MD_REPORT_BACKUP_PATH:-}"
  local migration_decision="${MD_REPORT_MIGRATION_DECISION:-not_reached}"
  local migration_schema_first="${MD_REPORT_MIGRATION_SCHEMA_FIRST:-not_reached}"
  local migration_post_sync="${MD_REPORT_MIGRATION_POST_SYNC:-not_reached}"
  local alembic_head="${MD_REPORT_ALEMBIC_HEAD:-}"
  local restart_result="${MD_REPORT_RESTART_RESULT:-not_reached}"
  local health_result="${MD_REPORT_HEALTH_RESULT:-not_reached}"
  local verify_result="${MD_REPORT_VERIFY_RESULT:-not_reached}"
  local smoke_result="${MD_REPORT_SMOKE_RESULT:-not_reached}"
  local partial_deploy="${MD_REPORT_PARTIAL_DEPLOY:-false}"
  local failed_stage="${MD_REPORT_FAILED_STAGE:-}"
  local failed_detail="${MD_REPORT_FAILED_STAGE_DETAIL:-}"
  local duration="${MD_REPORT_DURATION_SECONDS:-0}"
  local rollback
  rollback="$(md_rollback_recommendation "$failed_stage" "$outcome")"
  if [[ "$outcome" == "success" ]]; then
    failed_stage=""
    failed_detail=""
    partial_deploy="false"
    rollback="none"
  fi

  mkdir -p "$deploy_dir" || {
    echo "ERROR: cannot create deployments dir: $deploy_dir" >&2
    return 1
  }

  # Best-effort non-secret enrichments (never fail report write).
  local db_name="" kv="" mv="" qdrant_points=""
  if [[ -f "$project_root/.env" ]]; then
    db_name="$(grep -E '^DATABASE_URL=' "$project_root/.env" 2>/dev/null \
      | sed -E 's/.*@[^/]+\/([^?]+).*/\1/' | tail -1 || true)"
  fi
  if [[ -z "$alembic_head" ]] && curl -sf --max-time 3 "http://127.0.0.1:8000/api/build" -o /tmp/md-report-build.json 2>/dev/null; then
    alembic_head="$(python3 -c "import json; print(json.load(open('/tmp/md-report-build.json')).get('alembic_head') or '')" 2>/dev/null || true)"
    kv="$(python3 -c "import json; print(json.load(open('/tmp/md-report-build.json')).get('knowledge_version') or '')" 2>/dev/null || true)"
    mv="$(python3 -c "import json; print(json.load(open('/tmp/md-report-build.json')).get('memory_version') or '')" 2>/dev/null || true)"
  fi
  if curl -sf --max-time 3 "http://127.0.0.1:6333/collections/site_knowledge" -o /tmp/md-report-qdrant.json 2>/dev/null; then
    qdrant_points="$(python3 -c "import json; d=json.load(open('/tmp/md-report-qdrant.json')); print(d.get('result',{}).get('points_count',''))" 2>/dev/null || true)"
  fi

  local manifest_path="$deploy_dir/${ts}-${short}.json"
  local manifest_time
  manifest_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  REPORT_JSON_PATH="$manifest_path" python3 - <<PY
import json, os
from pathlib import Path
payload = {
    "outcome": os.environ.get("MD_REPORT_OUTCOME", "$outcome"),
    "deployed_commit": """$commit""",
    "deployed_commit_short": """$short""",
    "deployed_release": """$release""",
    "previous_commit": """$previous_commit""",
    "previous_release": """$previous_release""",
    "origin_main_commit": """$origin_main""",
    "project_root": """$project_root""",
    "backup_id": """$backup_id""",
    "backup_path": """$backup_path""",
    "migration_decision": """$migration_decision""",
    "migration_schema_first": """$migration_schema_first""",
    "migration_post_sync": """$migration_post_sync""",
    "alembic_head": """$alembic_head""",
    "restart_result": """$restart_result""",
    "health_result": """$health_result""",
    "verify_release_result": """$verify_result""",
    "smoke_result": """$smoke_result""",
    "partial_deploy": """$partial_deploy""",
    "failed_stage": """$failed_stage""",
    "failed_stage_detail": """$failed_detail""",
    "rollback_recommendation": """$rollback""",
    "duration_seconds": int(float("""$duration""") or 0),
    "operator": """$operator""",
    "manifest_time": """$manifest_time""",
    "manifest_path": """$manifest_path""",
    # Optional enrichments (non-secret)
    "database_name": """$db_name""",
    "knowledge_version": """$kv""",
    "memory_version": """$mv""",
    "qdrant_site_knowledge_points": """$qdrant_points""",
}
# Force outcome from env when set by caller after local defaults
if os.environ.get("MD_REPORT_OUTCOME"):
    payload["outcome"] = os.environ["MD_REPORT_OUTCOME"]
path = Path(os.environ["REPORT_JSON_PATH"])
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"OK: deployment report → {path}")
PY

  ln -sfn "$(basename "$manifest_path")" "$deploy_dir/latest.json"
  # latest.json should be a real pointer file for consumers that read it as JSON
  # (symlink to newest report is fine; also write a small pointer JSON).
  python3 - <<PY
import json
from pathlib import Path
pointer = {
    "latest": "$(basename "$manifest_path")",
    "manifest_path": "$manifest_path",
    "outcome": "$outcome",
    "manifest_time": "$manifest_time",
}
# Prefer symlink for family compatibility; if symlink exists, leave it.
# Also write latest.pointer.json for explicit newest reference.
Path("$deploy_dir/latest.pointer.json").write_text(json.dumps(pointer, indent=2) + "\n")
PY
  MD_REPORT_MANIFEST_PATH="$manifest_path"
  export MD_REPORT_MANIFEST_PATH
}

# Back-compat wrapper used by older call sites / tests.
md_write_deploy_manifest() {
  local project_root="$1"
  local commit="$2"
  local smoke_result="${3:-skipped}"
  MD_REPORT_OUTCOME="success"
  MD_REPORT_DEPLOYED_COMMIT="$commit"
  MD_REPORT_SMOKE_RESULT="$smoke_result"
  MD_REPORT_PARTIAL_DEPLOY="false"
  MD_REPORT_RESTART_RESULT="${MD_REPORT_RESTART_RESULT:-ok}"
  MD_REPORT_HEALTH_RESULT="${MD_REPORT_HEALTH_RESULT:-ok}"
  MD_REPORT_VERIFY_RESULT="${MD_REPORT_VERIFY_RESULT:-pass}"
  MD_REPORT_MIGRATION_DECISION="${MD_REPORT_MIGRATION_DECISION:-post_sync_only}"
  MD_REPORT_MIGRATION_SCHEMA_FIRST="${MD_REPORT_MIGRATION_SCHEMA_FIRST:-skipped}"
  MD_REPORT_MIGRATION_POST_SYNC="${MD_REPORT_MIGRATION_POST_SYNC:-ok}"
  md_write_deploy_report "$project_root"
}

md_show_latest_manifest() {
  local project_root="${1:-/opt/ai-site-agent}"
  local latest="$project_root/deployments/latest.json"
  if [[ -f "$latest" ]]; then
    python3 -m json.tool "$latest"
  else
    echo "No deployment manifest found at $latest"
    return 1
  fi
}
