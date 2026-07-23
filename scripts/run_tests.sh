#!/usr/bin/env bash
# Run backend tests inside the virtualenv.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/backend"
if [ -x ".venv/bin/pytest" ]; then
  exec .venv/bin/pytest
else
  exec python3 -m pytest
fi
