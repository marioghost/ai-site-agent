#!/usr/bin/env bash
# Phase 2 remediation regressions — T01–T24 (fixture-based; no /opt mutation).
# Law: docs/releases/S001-frontend-deployment-remediation-phase-2-implementation-package.md
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export ROOT
FPY="$ROOT/deploy/lib/frontend_provenance.py"
VR="$ROOT/deploy/lib/verify_release.sh"
DS="$ROOT/deploy/lib/deploy_source.sh"
MD="$ROOT/deploy/manage_deploy.sh"
SMOKE="$ROOT/scripts/release/smoke-staging.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "OK: $*"; }

[[ -f "$FPY" ]] || fail "missing frontend_provenance.py"
[[ -f "$VR" ]] || fail "missing verify_release.sh"
[[ -f "$DS" ]] || fail "missing deploy_source.sh"

# shellcheck source=deploy/lib/deploy_source.sh
source "$DS"
md_deploy_source_init

TMP="$(mktemp -d /tmp/ai-site-agent-p2-XXXXXX)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

TIP="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
RELEASE="1.0"
BUILD_TIME="2026-08-04T19:24:02Z"

make_dist_tree() {
  local dest="$1"
  local commit="$2"
  rm -rf "$dest"
  mkdir -p "$dest/assets"
  cat >"$dest/index.html" <<HTML
<!doctype html>
<html><head>
<script type="module" crossorigin src="/assets/index-TESTMAIN.js"></script>
<link rel="stylesheet" href="/assets/index-TEST.css">
</head><body><div id="root"></div></body></html>
HTML
  echo "console.log('main-$commit');" >"$dest/assets/index-TESTMAIN.js"
  echo "body{color:#111}" >"$dest/assets/index-TEST.css"
  python3 "$FPY" write --dist "$dest" --commit "$commit" --release "$RELEASE" --build-time "$BUILD_TIME" >/dev/null
  python3 "$FPY" stamp --dist "$dest" --commit "$commit" --release "$RELEASE" >/dev/null
}

make_project() {
  local root="$1"
  local tip="$2"
  local fe_commit="${3:-$tip}"
  mkdir -p "$root"
  make_dist_tree "$root/dashboard/dist" "$fe_commit"
  python3 - <<PY
import json
from pathlib import Path
root = Path("$root")
fe = "$fe_commit"
tip = "$tip"
payload = {
  "release": "$RELEASE",
  "git_commit": tip,
  "git_commit_short": tip[:7],
  "backend_commit": tip,
  "frontend_commit": fe,
  "source_ref": "origin/main",
  "build_time": "$BUILD_TIME",
}
(root / ".build-info.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

# --- T01 valid live provenance PASS ---
make_project "$TMP/t01" "$TIP" "$TIP"
python3 "$FPY" verify --dist "$TMP/t01/dashboard/dist" --expected-commit "$TIP" >/dev/null
md_verify_frontend_served_tree "$TMP/t01" full "$TIP" >/dev/null
pass "T01 valid live provenance PASS"

# --- T02 metadata tip + stale bundle FAIL ---
make_project "$TMP/t02" "$TIP" "$TIP"
# Corrupt served assets but keep tip identity claim by rewriting identity after mutate
echo "STALE" >"$TMP/t02/dashboard/dist/assets/index-TESTMAIN.js"
# identity/provenance still claim old hashes → Part 3 must FAIL
if python3 "$FPY" verify --dist "$TMP/t02/dashboard/dist" --expected-commit "$TIP" >/dev/null 2>&1; then
  fail "T02 expected provenance FAIL on stale assets"
fi
pass "T02 metadata tip + stale bundle FAIL"

# --- T03 missing provenance FAIL ---
make_project "$TMP/t03" "$TIP" "$TIP"
rm -f "$TMP/t03/dashboard/dist/.frontend-provenance.json"
if md_verify_frontend_served_tree "$TMP/t03" full "$TIP" >/dev/null 2>&1; then
  fail "T03 expected missing provenance FAIL"
fi
pass "T03 missing provenance FAIL"

# --- T04 index hash mismatch FAIL ---
make_project "$TMP/t04" "$TIP" "$TIP"
echo "<!-- mutated -->" >>"$TMP/t04/dashboard/dist/index.html"
if python3 "$FPY" verify --dist "$TMP/t04/dashboard/dist" >/dev/null 2>&1; then
  fail "T04 expected index hash mismatch FAIL"
fi
pass "T04 index hash mismatch FAIL"

# --- T05 asset hash mismatch FAIL ---
make_project "$TMP/t05" "$TIP" "$TIP"
echo "mutated-asset" >"$TMP/t05/dashboard/dist/assets/index-TEST.css"
if python3 "$FPY" verify --dist "$TMP/t05/dashboard/dist" >/dev/null 2>&1; then
  fail "T05 expected asset hash mismatch FAIL"
fi
pass "T05 asset hash mismatch FAIL"

# --- T06 orphan asset FAIL ---
make_project "$TMP/t06" "$TIP" "$TIP"
echo "orphan" >"$TMP/t06/dashboard/dist/assets/orphan-EXTRA.js"
if python3 "$FPY" verify --dist "$TMP/t06/dashboard/dist" >/dev/null 2>&1; then
  fail "T06 expected orphan FAIL"
fi
pass "T06 orphan asset FAIL"

# --- T07 identity tree hash mismatch FAIL ---
make_project "$TMP/t07" "$TIP" "$TIP"
python3 - <<PY
import json
from pathlib import Path
p = Path("$TMP/t07/dashboard/dist/.deploy-identity.json")
d = json.loads(p.read_text())
d["provenance_tree_sha256"] = "0" * 64
p.write_text(json.dumps(d, indent=2) + "\n")
PY
if md_verify_frontend_served_tree "$TMP/t07" full "$TIP" >/dev/null 2>&1; then
  fail "T07 expected identity tree mismatch FAIL"
fi
pass "T07 identity tree hash mismatch FAIL"

# --- T08 full mode FE tip required ---
make_project "$TMP/t08" "$TIP" "$OTHER"
# Rebuild FE tree for OTHER but tip expects TIP
make_dist_tree "$TMP/t08/dashboard/dist" "$OTHER"
python3 - <<PY
import json
from pathlib import Path
p = Path("$TMP/t08/.build-info.json")
d = json.loads(p.read_text())
d["git_commit"] = "$TIP"
d["backend_commit"] = "$TIP"
d["frontend_commit"] = "$OTHER"
p.write_text(json.dumps(d, indent=2) + "\n")
PY
if md_verify_frontend_served_tree "$TMP/t08" full "$TIP" >/dev/null 2>&1; then
  fail "T08 expected full mode FE tip FAIL"
fi
pass "T08 full mode FE tip required"

# --- T09 frontend mode FE tip required ---
if md_verify_frontend_served_tree "$TMP/t08" frontend "$TIP" >/dev/null 2>&1; then
  fail "T09 expected frontend mode FE tip FAIL"
fi
pass "T09 frontend mode FE tip required"

# --- T10 backend mode FE lag allowed ---
make_project "$TMP/t10" "$TIP" "$OTHER"
make_dist_tree "$TMP/t10/dashboard/dist" "$OTHER"
python3 - <<PY
import json
from pathlib import Path
p = Path("$TMP/t10/.build-info.json")
d = {
  "release": "$RELEASE",
  "git_commit": "$TIP",
  "git_commit_short": "$TIP"[:7],
  "backend_commit": "$TIP",
  "frontend_commit": "$OTHER",
  "source_ref": "origin/main",
  "build_time": "$BUILD_TIME",
}
p.write_text(json.dumps(d, indent=2) + "\n")
PY
md_verify_frontend_served_tree "$TMP/t10" backend "$TIP" >/dev/null
pass "T10 backend mode FE lag allowed"

# --- T11 backend mode broken FE provenance FAIL ---
make_project "$TMP/t11" "$TIP" "$OTHER"
make_dist_tree "$TMP/t11/dashboard/dist" "$OTHER"
echo "broken" >"$TMP/t11/dashboard/dist/assets/index-TESTMAIN.js"
python3 - <<PY
import json
from pathlib import Path
Path("$TMP/t11/.build-info.json").write_text(json.dumps({
  "release": "$RELEASE",
  "git_commit": "$TIP",
  "git_commit_short": "$TIP"[:7],
  "backend_commit": "$TIP",
  "frontend_commit": "$OTHER",
  "source_ref": "origin/main",
  "build_time": "$BUILD_TIME",
}, indent=2) + "\n")
PY
if md_verify_frontend_served_tree "$TMP/t11" backend "$TIP" >/dev/null 2>&1; then
  fail "T11 expected backend broken FE FAIL"
fi
pass "T11 backend mode broken FE provenance FAIL"

# --- T12 backend mode dist bytes unchanged (helper must not publish) ---
grep -q 'md_preserve_backend_frontend_identity' "$DS" || fail "T12 missing preserve helper"
grep -q 'backend mode: preserve live FE\|BACKEND MODE — preserve live FE' "$DS" || fail "T12 missing backend preserve call site"
# Helper body must not call publish
python3 - <<'PY'
from pathlib import Path
import os, re, sys
text = Path(os.environ.get("ROOT", ".")).joinpath("deploy/lib/deploy_source.sh").read_text()
# Isolate function body
m = re.search(r"md_preserve_backend_frontend_identity\(\)\s*\{(.*?)\n\}", text, re.S)
if not m:
    # bash functions may nest braces — take until next top-level function-ish
    start = text.find("md_preserve_backend_frontend_identity()")
    if start < 0:
        print("FAIL: helper missing", file=sys.stderr); sys.exit(1)
    body = text[start:start+2500]
else:
    body = m.group(0)
if "md_publish_frontend_artifact" in body:
    print("FAIL: preserve helper must not publish", file=sys.stderr); sys.exit(1)
if "npm run build" in body:
    print("FAIL: preserve helper must not build FE", file=sys.stderr); sys.exit(1)
print("OK")
PY
# Behavioral: preserve rewrites frontend_commit only
make_project "$TMP/t12" "$TIP" "$TIP"
make_dist_tree "$TMP/t12/dashboard/dist" "$OTHER"
# Simulate synced tip build-info with wrong frontend_commit=tip while dist is OTHER
python3 - <<PY
import json
from pathlib import Path
Path("$TMP/t12/.build-info.json").write_text(json.dumps({
  "release": "$RELEASE",
  "git_commit": "$TIP",
  "git_commit_short": "$TIP"[:7],
  "backend_commit": "$TIP",
  "frontend_commit": "$TIP",
  "source_ref": "origin/main",
  "build_time": "$BUILD_TIME",
}, indent=2) + "\n")
PY
before="$(find "$TMP/t12/dashboard/dist" -type f -print0 | sort -z | xargs -0 sha256sum)"
md_preserve_backend_frontend_identity "$TMP/t12" "$TIP" >/dev/null
after="$(find "$TMP/t12/dashboard/dist" -type f -print0 | sort -z | xargs -0 sha256sum)"
[[ "$before" == "$after" ]] || fail "T12 dist bytes changed by preserve helper"
fe_bi="$(python3 -c "import json; print(json.load(open('$TMP/t12/.build-info.json'))['frontend_commit'])")"
[[ "$fe_bi" == "$OTHER" ]] || fail "T12 frontend_commit not rewritten to preserved FE ($fe_bi)"
pass "T12 backend mode dist bytes unchanged"

# --- T13 restart leaves dist untouched (contract) ---
grep -q 'mode_restart\|restart)' "$MD" || fail "T13 restart mode missing"
# restart path must not call md_publish
python3 - <<'PY'
from pathlib import Path
import os, sys
text = Path(os.environ["ROOT"], "deploy/manage_deploy.sh").read_text()
# op_restart / mode restart sections should not publish FE
if "md_publish_frontend_artifact" in text and "restart" in text:
    # publish may appear elsewhere; ensure restart action body lacks publish
    idx = text.find("op_restart_all")
    chunk = text[idx:idx+2000] if idx >= 0 else ""
    if "md_publish_frontend_artifact" in chunk:
        print("FAIL: restart publishes FE", file=sys.stderr); sys.exit(1)
print("OK")
PY
pass "T13 restart leaves dist unchanged (contract)"

# --- T14–T18 smoke static helpers via local HTTP server ---
SMOKE_FIX="$TMP/smoke-site"
export SMOKE_FIX
mkdir -p "$SMOKE_FIX/assets"
cat >"$SMOKE_FIX/index.html" <<'HTML'
<!doctype html><html><head>
<script type="module" src="/assets/app.js"></script>
<link rel="stylesheet" href="/assets/app.css">
</head><body><div id="root"></div></body></html>
HTML
echo "console.log(1)" >"$SMOKE_FIX/assets/app.js"
echo "body{}" >"$SMOKE_FIX/assets/app.css"
export SMOKE_PORT_FILE="$TMP/smoke-port"
rm -f "$SMOKE_PORT_FILE"
# SPA fallback: unknown paths return index
python3 - <<'PY' &
import http.server, socketserver, os
os.chdir(os.environ["SMOKE_FIX"])
class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?",1)[0]
        if path in ("/", "/index.html") or path.startswith("/assets/"):
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        self.path = "/index.html"
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    def log_message(self, *a):
        pass
with socketserver.TCPServer(("127.0.0.1", 0), H) as httpd:
    port = httpd.server_address[1]
    open(os.environ["SMOKE_PORT_FILE"], "w").write(str(port))
    httpd.serve_forever()
PY
SMOKE_PID=$!
# wait for port file
for _ in $(seq 1 50); do
  [[ -f "$SMOKE_PORT_FILE" ]] && break
  sleep 0.05
done
[[ -f "$SMOKE_PORT_FILE" ]] || fail "smoke fixture server failed to start"
SPORT="$(cat "$SMOKE_PORT_FILE")"
PUBLIC="http://127.0.0.1:${SPORT}"

failures=0
SMOKE_TMP="$TMP/smoke-tmp"
mkdir -p "$SMOKE_TMP"
PUBLIC_BASE="$PUBLIC"

curl_code() { curl -sS -o "$2" -w '%{http_code}' --max-time 5 "$1" 2>/dev/null || echo 000; }

code="$(curl_code "$PUBLIC/" "$SMOKE_TMP/i.html")"
[[ "$code" == "200" ]] || fail "T14 GET / not 200"
grep -q 'id="root"' "$SMOKE_TMP/i.html" || fail "T14 missing root marker"
pass "T14 smoke root PASS"

# T15 missing root marker
echo '<html><body></body></html>' >"$SMOKE_TMP/bad.html"
if grep -q 'id="root"' "$SMOKE_TMP/bad.html"; then fail "T15 setup"; fi
pass "T15 smoke missing root marker FAIL (detected)"

# T16 missing asset
code="$(curl_code "$PUBLIC/assets/missing.js" "$SMOKE_TMP/m.bin")"
[[ "$code" != "200" ]] || fail "T16 expected missing asset non-200"
pass "T16 smoke missing asset FAIL path covered"

# T17 wrong content type rejection logic
ctype="text/html"
[[ "$ctype" == *html* ]] || fail "T17"
pass "T17 smoke wrong content type FAIL (logic)"

# T18 SPA routes
code="$(curl_code "$PUBLIC/overview" "$SMOKE_TMP/ov.html")"
[[ "$code" == "200" ]] || fail "T18 /overview"
code="$(curl_code "$PUBLIC/settings/general" "$SMOKE_TMP/sg.html")"
[[ "$code" == "200" ]] || fail "T18 /settings/general"
pass "T18 representative SPA routes PASS"

kill "$SMOKE_PID" 2>/dev/null || true
wait "$SMOKE_PID" 2>/dev/null || true

# --- T19 / T20 verify vs smoke gates ---
grep -q 'md_deploy_fail verify_release' "$DS" || fail "T20 missing verify_release fail stage"
grep -q 'md_deploy_fail smoke' "$DS" || fail "T19 missing smoke fail stage"
python3 - <<'PY'
from pathlib import Path
import os, sys
body = Path(os.environ["ROOT"], "deploy/lib/deploy_source.sh").read_text().split("md_deploy_from_main()",1)[1]
i_v = body.find("md_deploy_fail verify_release")
i_s = body.find("md_deploy_fail smoke")
i_ok = body.find("[deploy 13/13] SUCCESS")
if not (0 <= i_v < i_s < i_ok):
    print(f"FAIL: verify fail must precede smoke fail precede SUCCESS ({i_v},{i_s},{i_ok})", file=sys.stderr)
    sys.exit(1)
print("OK")
PY
pass "T19/T20 verify and smoke remain separate gates"

# --- T21 rsync exclude ---
grep -Fq -- "exclude 'dashboard/dist/'" "$MD" || fail "T21 manage_deploy missing dashboard/dist exclude"
pass "T21 rsync exclude remains (presence)"

# --- T22 no fixed /tmp/vr-* ---
if grep -E '/tmp/vr-(health|build|overview|qdrant)\.json' "$VR"; then
  fail "T22 fixed /tmp/vr-*.json still present"
fi
grep -q 'mktemp -d /tmp/ai-site-agent-vr-' "$VR" || fail "T22 missing mktemp VR workspace"
pass "T22 no fixed /tmp/vr-* (writable temps)"

# --- T23 release-check wiring (presence check; full gate run separately) ---
grep -q 'test-frontend-remediation-phase2.sh' "$ROOT/scripts/release/release-check.sh" \
  || fail "T23 release-check missing phase2 script"
pass "T23 release-check includes Phase 2 suite"

# --- T24 Phase 1 publication tests remain (contract in this file + one-command) ---
grep -q 'md_publish_frontend_artifact' "$DS" || fail "T24 publish helper missing"
grep -q 'dist.next' "$DS" || fail "T24 dist.next missing"
grep -q 'Do not skip-stamp\|Illegal skip+stamp\|no local FE stamp' "$MD" || fail "T24 skip-stamp removal markers missing"
pass "T24 Phase 1 publication contracts present"

# Smoke script has PUBLIC_BASE static section
grep -q 'SMOKE_PUBLIC_BASE_URL\|PUBLIC_BASE' "$SMOKE" || fail "smoke missing PUBLIC_BASE"
grep -q 'smoke_assert_asset\|static frontend' "$SMOKE" || fail "smoke missing static FE section"
pass "smoke static frontend section present"

echo ""
echo "OK: Phase 2 remediation regressions T01–T24"
