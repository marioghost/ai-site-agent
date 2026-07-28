#!/usr/bin/env bash
# HTTP smoke against running backend (paths/creds from scripts/lib/deploy-env.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Prefer deploy-env; fall back to .env.staging if present (legacy).
# shellcheck disable=SC1091
source "$ROOT/scripts/lib/deploy-env.sh"

if [[ -f "$ROOT/.env.staging" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT/.env.staging"
  set +a
fi

export STAGING_BASE_URL STAGING_ADMIN_USER STAGING_ADMIN_PASSWORD

ROOT="$ROOT"
BACKEND="$ROOT/backend"
VENV="${BACKEND}/.venv"

BASE="${STAGING_BASE_URL:-http://127.0.0.1:8000}"
ADMIN_USER="${STAGING_ADMIN_USER:-admin}"
ADMIN_PASSWORD="${STAGING_ADMIN_PASSWORD:-фвьшт}"
SEED_PASSWORD="фвьшт"

failures=0
pass() { echo "OK: $*"; }
warn() { echo "WARN: $*"; }
fail() { echo "FAIL: $*"; failures=$((failures + 1)); }

curl_json() {
  curl -sf --max-time "${CURL_TIMEOUT:-30}" "$@"
}

# Retry flaky post-restart probes (connection refused / brief warmup).
curl_json_retry() {
  local url="$1"
  shift
  local attempt
  for attempt in 1 2 3 4 5 6 7 8; do
    if curl_json "$url" "$@"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

echo "==> Smoke: $BASE"

if curl_json_retry "$BASE/api/health" -o /tmp/staging-health.json; then
  pass "GET /api/health"
  python3 -c "import json; d=json.load(open('/tmp/staging-health.json')); assert d.get('app',{}).get('status')=='ok', d"
else
  fail "GET /api/health unreachable"
fi

if curl_json_retry "$BASE/api/metrics" | grep -q 'kos_memory_version'; then
  pass "GET /api/metrics (Prometheus)"
else
  fail "GET /api/metrics missing kos_memory_version"
fi

if curl_json_retry "$BASE/api/metrics/operational" -o /tmp/staging-metrics.json; then
  pass "GET /api/metrics/operational"
  python3 -c "import json; d=json.load(open('/tmp/staging-metrics.json')); assert 'memory_version' in d and 'knowledge_version' in d"
else
  fail "GET /api/metrics/operational"
fi

if curl_json_retry "$BASE/api/build" -o /tmp/staging-build.json; then
  pass "GET /api/build"
  python3 -c "import json; d=json.load(open('/tmp/staging-build.json')); \
assert d.get('release') and d.get('alembic_head') and 'memory_version' in d and 'feature_flags' in d"
else
  fail "GET /api/build"
fi

TOKEN=""
LOGIN_HTTP="$(curl -sS -o /tmp/staging-login.json -w '%{http_code}' --max-time 30 -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASSWORD\"}" || true)"
if [[ "$LOGIN_HTTP" == "200" ]]; then
  TOKEN="$(python3 -c "import json; print(json.load(open('/tmp/staging-login.json'))['access_token'])")"
  pass "POST /api/auth/login"
elif [[ "$LOGIN_HTTP" == "401" ]]; then
  fail "POST /api/auth/login (401 Unauthorized)"
  if [[ "$ADMIN_PASSWORD" == "$SEED_PASSWORD" ]]; then
    echo "HINT: seed password does not match this DB (password was likely changed)." >&2
    echo "HINT: set STAGING_ADMIN_PASSWORD in deploy/deploy.local.conf or repo .env, then re-run:" >&2
    echo "HINT:   bash deploy/manage_deploy.sh smoke" >&2
  else
    echo "HINT: check STAGING_ADMIN_USER / STAGING_ADMIN_PASSWORD for user '$ADMIN_USER'" >&2
  fi
else
  fail "POST /api/auth/login (HTTP ${LOGIN_HTTP:-curl-failed})"
fi

if [[ -n "$TOKEN" ]]; then
  if curl_json "$BASE/api/settings" -H "Authorization: Bearer $TOKEN" -o /tmp/staging-settings.json; then
    pass "GET /api/settings (authenticated)"
    python3 -c "import json; d=json.load(open('/tmp/staging-settings.json')); \
assert all(k in d for k in ('knowledge_version','memory_version','cache_namespace_v2_enabled','enable_semantic_diagnostics_v2'))"
  else
    fail "GET /api/settings"
  fi
fi

if [[ "${SMOKE_CHAT:-0}" == "1" && -n "$TOKEN" ]]; then
  CHAT_PAYLOAD='{"message":"What is on the homepage?","debug":false,"bypass_cache":true}'
  if CHAT_JSON="$(curl -sf --max-time 120 -X POST "$BASE/api/chat" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$CHAT_PAYLOAD")"; then
    pass "POST /api/chat (flags OFF path)"
    python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('answer')" <<< "$CHAT_JSON"
  else
    warn "POST /api/chat failed — is Ollama running? (set SMOKE_CHAT=0 to skip)"
  fi
else
  echo "SKIP: POST /api/chat (set SMOKE_CHAT=1 to enable)"
fi

if [[ -x "$VENV/bin/pytest" ]]; then
  echo "==> Golden unit parity"
  cd "$BACKEND"
  if "$VENV/bin/pytest" tests/test_golden_chat_parity.py tests/test_golden_queries_schema.py -m unit -q; then
    pass "golden unit parity"
  else
    fail "golden unit parity"
  fi
fi

echo ""
if [[ "$failures" -eq 0 ]]; then
  echo "OK: smoke passed"
  exit 0
fi

echo "FAIL: smoke had $failures failure(s)"
exit 1
