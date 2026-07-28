#!/usr/bin/env bash
# Deployment state manifest — written after each deploy.
set -euo pipefail

md_write_deploy_manifest() {
  local project_root="$1"
  local commit="$2"
  local smoke_result="${3:-skipped}"
  local deploy_dir="$project_root/deployments"
  local ts operator db_name alembic_head backup_path
  ts="$(date -u +%Y%m%d_%H%M%S)"
  operator="${SUDO_USER:-${USER:-unknown}}"
  mkdir -p "$deploy_dir"

  db_name=""
  alembic_head=""
  if [[ -f "$project_root/.env" ]]; then
    # Parse DATABASE_URL database name without printing secrets.
    db_name="$(grep -E '^DATABASE_URL=' "$project_root/.env" | sed -E 's/.*@[^/]+\/([^?]+).*/\1/' | tail -1)"
  fi

  local build_json="$project_root/.build-info.json"
  local release="?" git_short="?" build_time="?"
  if [[ -f "$build_json" ]]; then
    release="$(python3 -c "import json; print(json.load(open('$build_json')).get('release','?'))" 2>/dev/null || echo "?")"
    git_short="$(python3 -c "import json; print(json.load(open('$build_json')).get('git_commit_short','?'))" 2>/dev/null || echo "?")"
    build_time="$(python3 -c "import json; print(json.load(open('$build_json')).get('build_time','?'))" 2>/dev/null || echo "?")"
  fi

  backup_path="$(ls -1t "$project_root/backups/"*.dump 2>/dev/null | head -1 || echo "")"
  local manifest_path="$deploy_dir/${ts}-${git_short}.json"

  local kv mv qdrant_points
  kv="" mv="" qdrant_points=""
  if curl -sf --max-time 5 "http://127.0.0.1:8000/api/build" -o /tmp/md-manifest-build.json 2>/dev/null; then
    alembic_head="$(python3 -c "import json; d=json.load(open('/tmp/md-manifest-build.json')); print(d.get('alembic_head',''))" 2>/dev/null || true)"
    kv="$(python3 -c "import json; d=json.load(open('/tmp/md-manifest-build.json')); print(d.get('knowledge_version',''))" 2>/dev/null || true)"
    mv="$(python3 -c "import json; d=json.load(open('/tmp/md-manifest-build.json')); print(d.get('memory_version',''))" 2>/dev/null || true)"
  fi
  if curl -sf --max-time 5 "http://127.0.0.1:6333/collections/site_knowledge" -o /tmp/md-qdrant.json 2>/dev/null; then
    qdrant_points="$(python3 -c "import json; d=json.load(open('/tmp/md-qdrant.json')); print(d['result'].get('points_count',''))" 2>/dev/null || true)"
  fi

  python3 - <<PY
import json
from pathlib import Path
payload = {
    "release": "$release",
    "git_commit": "$commit",
    "git_commit_short": "$git_short",
    "origin_main_commit": "$commit",
    "build_time": "$build_time",
    "manifest_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "operator": "$operator",
    "database_name": "$db_name",
    "alembic_head": "$alembic_head",
    "knowledge_version": "$kv",
    "memory_version": "$mv",
    "qdrant_site_knowledge_points": "$qdrant_points",
    "backup_path": "$backup_path",
    "smoke_result": "$smoke_result",
    "project_root": "$project_root",
}
Path("$manifest_path").write_text(json.dumps(payload, indent=2) + "\n")
print(f"OK: deployment manifest → $manifest_path")
PY
  ln -sf "$(basename "$manifest_path")" "$deploy_dir/latest.json" 2>/dev/null || true
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
