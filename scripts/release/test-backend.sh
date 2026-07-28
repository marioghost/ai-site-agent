#!/usr/bin/env bash
# Backend unit test suite (RFC migration gate).
# Pure unit tests never require Postgres. DB modules need disposable POSTGRES_TEST_URL.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "$ROOT/scripts/release/test-backend-unit.sh" "$@"
