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

# Per-run temp dir — shared /tmp/staging-*.json breaks under sticky /tmp when
# smoke alternates between sudo (root) and the interactive user (curl error 23).
SMOKE_TMP="$(mktemp -d /tmp/ai-site-agent-smoke-XXXXXX)"
cleanup_smoke_tmp() { rm -rf "$SMOKE_TMP"; }
trap cleanup_smoke_tmp EXIT

failures=0
pass() { echo "OK: $*"; }
warn() { echo "WARN: $*"; }
fail() { echo "FAIL: $*"; failures=$((failures + 1)); }

# Public site base for static FE checks (nginx), NOT the API BASE.
PUBLIC_BASE="${SMOKE_PUBLIC_BASE_URL:-http://127.0.0.1}"
PUBLIC_BASE="${PUBLIC_BASE%/}"

smoke_fetch_public() {
  local path="$1"
  local out="$2"
  local code
  code="$(curl -sS -o "$out" -w '%{http_code}' --max-time "${CURL_TIMEOUT:-30}" "${PUBLIC_BASE}${path}" 2>/dev/null || echo "000")"
  if [[ "$code" != "200" ]]; then
    fail "GET ${PUBLIC_BASE}${path} (HTTP $code)"
    return 1
  fi
  return 0
}

smoke_assert_root_marker() {
  local file="$1"
  if grep -q 'id="root"' "$file"; then
    pass "public / root mount marker id=\"root\""
    return 0
  fi
  fail "public / missing root mount marker id=\"root\""
  return 1
}

smoke_parse_index_assets() {
  local file="$1"
  python3 - "$file" <<'PY'
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore")
refs = re.findall(r"""(?:src|href)\s*=\s*["'](/assets/[^"']+)["']""", text, flags=re.I)
# unique preserve order
seen = set()
out = []
for r in refs:
    if r not in seen:
        seen.add(r)
        out.append(r)
if not out:
    sys.exit(2)
print("\n".join(out))
PY
}

smoke_assert_asset() {
  local path="$1"
  local tmp="$SMOKE_TMP/asset-meta.txt"
  local code ctype
  # Fetch headers + body status
  code="$(curl -sS -o "$SMOKE_TMP/asset-body.bin" -D "$tmp" -w '%{http_code}' --max-time "${CURL_TIMEOUT:-30}" "${PUBLIC_BASE}${path}" 2>/dev/null || echo "000")"
  if [[ "$code" != "200" ]]; then
    fail "GET ${PUBLIC_BASE}${path} (HTTP $code)"
    return 1
  fi
  ctype="$(tr -d '\r' <"$tmp" | awk -F': ' 'tolower($1)=="content-type"{print tolower($2); exit}')"
  ctype="${ctype%%;*}"
  case "$path" in
    *.js)
      if [[ "$ctype" != *javascript* && "$ctype" != "application/octet-stream" ]]; then
        fail "GET ${PUBLIC_BASE}${path} bad Content-Type ($ctype) — reject text/html SPA fallback"
        return 1
      fi
      if [[ "$ctype" == *html* ]]; then
        fail "GET ${PUBLIC_BASE}${path} Content-Type text/html (missing asset)"
        return 1
      fi
      ;;
    *.css)
      if [[ "$ctype" != *css* ]]; then
        fail "GET ${PUBLIC_BASE}${path} bad Content-Type ($ctype)"
        return 1
      fi
      if [[ "$ctype" == *html* ]]; then
        fail "GET ${PUBLIC_BASE}${path} Content-Type text/html (missing asset)"
        return 1
      fi
      ;;
    *)
      if [[ "$ctype" == *html* ]]; then
        fail "GET ${PUBLIC_BASE}${path} Content-Type text/html (missing asset)"
        return 1
      fi
      ;;
  esac
  pass "GET ${path} (200, $ctype)"
  return 0
}

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

if curl_json_retry "$BASE/api/health" -o "$SMOKE_TMP/health.json"; then
  pass "GET /api/health"
  python3 -c "import json; d=json.load(open('$SMOKE_TMP/health.json')); assert d.get('app',{}).get('status')=='ok', d"
else
  fail "GET /api/health unreachable"
fi

if curl_json_retry "$BASE/api/metrics" | grep -q 'kos_memory_version'; then
  pass "GET /api/metrics (Prometheus)"
else
  fail "GET /api/metrics missing kos_memory_version"
fi

if curl_json_retry "$BASE/api/metrics/operational" -o "$SMOKE_TMP/metrics.json"; then
  pass "GET /api/metrics/operational"
  python3 -c "import json; d=json.load(open('$SMOKE_TMP/metrics.json')); assert 'memory_version' in d and 'knowledge_version' in d"
else
  fail "GET /api/metrics/operational"
fi

if curl_json_retry "$BASE/api/build" -o "$SMOKE_TMP/build.json"; then
  pass "GET /api/build"
  python3 -c "import json; d=json.load(open('$SMOKE_TMP/build.json')); \
assert d.get('release') and d.get('alembic_head') and 'memory_version' in d and 'feature_flags' in d"
else
  fail "GET /api/build"
fi

TOKEN=""
LOGIN_HTTP="$(curl -sS -o "$SMOKE_TMP/login.json" -w '%{http_code}' --max-time 30 -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASSWORD\"}" 2>/dev/null || true)"
if [[ "$LOGIN_HTTP" == "200" ]]; then
  TOKEN="$(python3 -c "import json; print(json.load(open('$SMOKE_TMP/login.json'))['access_token'])")"
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
  if curl_json "$BASE/api/settings" -H "Authorization: Bearer $TOKEN" -o "$SMOKE_TMP/settings.json"; then
    pass "GET /api/settings (authenticated)"
    python3 -c "import json; d=json.load(open('$SMOKE_TMP/settings.json')); \
assert all(k in d for k in ('knowledge_version','memory_version','cache_namespace_v2_enabled','enable_semantic_diagnostics_v2'))"
  else
    fail "GET /api/settings"
  fi
fi

# --- Phase 2 B: static frontend checks against public site (nginx), not API BASE ---
echo "==> Smoke static frontend: $PUBLIC_BASE"
if smoke_fetch_public "/" "$SMOKE_TMP/public-index.html"; then
  pass "GET ${PUBLIC_BASE}/"
  smoke_assert_root_marker "$SMOKE_TMP/public-index.html" || true
  ASSET_LIST=""
  if ASSET_LIST="$(smoke_parse_index_assets "$SMOKE_TMP/public-index.html")"; then
    while IFS= read -r asset_path; do
      [[ -z "$asset_path" ]] && continue
      smoke_assert_asset "$asset_path" || true
    done <<< "$ASSET_LIST"
  else
    fail "public / has no /assets/ references"
  fi
fi
smoke_fetch_public "/overview" "$SMOKE_TMP/public-overview.html" && pass "GET ${PUBLIC_BASE}/overview" || true
smoke_fetch_public "/settings/general" "$SMOKE_TMP/public-settings-general.html" && pass "GET ${PUBLIC_BASE}/settings/general" || true

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
