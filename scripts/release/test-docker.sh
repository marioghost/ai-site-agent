#!/usr/bin/env bash
# Optional Docker build validation — skipped when docker or Dockerfile missing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DOCKERFILE="$ROOT/deploy/Dockerfile.validate"

if ! command -v docker &>/dev/null; then
  echo "SKIP: docker not installed"
  exit 0
fi

if [[ ! -f "$DOCKERFILE" ]]; then
  echo "SKIP: $DOCKERFILE not found"
  exit 0
fi

echo "==> Docker build validation (pip install smoke)"
docker build -f "$DOCKERFILE" -t ai-site-agent-validate:local "$ROOT"

echo "OK: docker build validation passed"
