#!/usr/bin/env bash
# Write .build-info.json at repo root (rsynced to /opt on deploy).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/.build-info.json"

GIT_COMMIT="unknown"
if command -v git &>/dev/null && git -C "$ROOT" rev-parse --is-inside-work-tree &>/dev/null; then
  GIT_COMMIT="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
  GIT_SHORT="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
else
  GIT_SHORT="unknown"
fi

BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RELEASE="${RELEASE_VERSION:-0.6}"

python3 - <<PY
import json
from pathlib import Path

payload = {
    "release": "${RELEASE}",
    "git_commit": "${GIT_COMMIT}",
    "git_commit_short": "${GIT_SHORT}",
    "build_time": "${BUILD_TIME}",
}
Path("${OUT}").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"OK: wrote {payload['git_commit_short']} @ {payload['build_time']} → ${OUT}")
PY
