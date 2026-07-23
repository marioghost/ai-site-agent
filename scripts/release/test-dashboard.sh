#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DASH="$ROOT/dashboard"

cd "$DASH"

if [[ ! -d node_modules ]]; then
  echo "==> npm install"
  npm install --silent
fi

echo "==> Dashboard vitest"
npm test

echo "==> TypeScript check"
npx tsc --noEmit

echo "==> Dashboard production build"
npm run build

echo "OK: dashboard tests and build passed"
