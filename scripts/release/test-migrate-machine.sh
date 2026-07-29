#!/usr/bin/env bash
# Regression: one-command machine migration orchestrator.
#
# Never touches ai_site_agent, live Qdrant, or live services. State, manifest,
# comparison and parity logic are exercised against fixtures in a temp dir.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MD="$ROOT/deploy/manage_deploy.sh"
CLI="$ROOT/deploy/lib/cli.sh"
MM="$ROOT/deploy/lib/migrate_machine.sh"
PY="$ROOT/deploy/lib/migrate_machine.py"

pass() { echo "OK: $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

[[ -f "$MM" ]] || fail "missing migrate_machine.sh"
[[ -f "$PY" ]] || fail "missing migrate_machine.py"

TMP="$(mktemp -d /tmp/mm-test-XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

py() { python3 "$PY" "$@"; }

# Extract one shell function body. Ends only on a lone "}" at column 0, so
# embedded Python heredocs (which contain lines starting with "}") do not
# truncate the range.
fn_body() { awk -v fn="$1" '$0 ~ "^"fn"\\(\\) \\{" {f=1} f {print} f && /^\}$/ {exit}' "$MM"; }

# --------------------------------------------------------------------------
# 1-2. host-role detection, ambiguity fails closed
# --------------------------------------------------------------------------
# shellcheck source=deploy/lib/migrate_machine.sh
source "$MM"

grep -q 'md_mm_detect_role' "$MM" || fail "role detection missing"
grep -q 'Host role is ambiguous' "$MM" || fail "ambiguous role message missing"
grep -q 'MM-ROLE01' "$MM" || fail "ambiguous role needs a stable error code"

# Exercise detection against stubbed observable state, one case per subshell.
detect_role_with() {
  # Stub return codes live in uniquely named globals: md_mm_detect_role declares
  # locals called live/bundle, and bash scoping is dynamic.
  local stub_live_rc="$1" stub_bundle_rc="$2" build_info="$3" dir="$4"
  (
    # shellcheck disable=SC1090
    source "$MM"
    MD_MM_LIB="$ROOT/deploy/lib"
    MD_MM_DIR="$dir"
    MD_MM_BUNDLE_DIR="$dir/bundle"
    MD_MM_BUILD_INFO="$build_info"
    md_mm_has_live_corpus() { return "$stub_live_rc"; }
    md_mm_has_bundle() { return "$stub_bundle_rc"; }
    md_mm_detect_role >/dev/null 2>&1 || { echo "AMBIGUOUS"; exit 0; }
    echo "$MD_MM_ROLE"
  )
}
mkdir -p "$TMP/r1" "$TMP/r2" "$TMP/r3" "$TMP/r4"
echo '{"release":"0.8"}' > "$TMP/build-info.json"

r="$(detect_role_with 0 1 "$TMP/build-info.json" "$TMP/r1")"
[[ "$r" == "source" ]] || fail "live corpus without a bundle must be the source (got $r)"
r="$(detect_role_with 1 0 "$TMP/build-info.json" "$TMP/r2")"
[[ "$r" == "target" ]] || fail "an incoming bundle must be the target (got $r)"
r="$(detect_role_with 1 1 "$TMP/missing.json" "$TMP/r3")"
[[ "$r" == "target" ]] || fail "a host with no build and no corpus must be the target (got $r)"

# Recorded role wins over heuristics, which is what makes resume deterministic.
py state-init --dir "$TMP/r4" --role target --migration-id mig-r >/dev/null
r="$(detect_role_with 0 1 "$TMP/build-info.json" "$TMP/r4")"
[[ "$r" == "target" ]] || fail "recorded role must override live-corpus heuristics (got $r)"
grep -q 'Recorded role always wins' "$MM" || fail "recorded role precedence must be stated"
pass "1. host-role detection resolves source, target, and prefers recorded role"

# Ambiguity: both a live corpus and an incoming bundle -> never guess.
mkdir -p "$TMP/ambig"
r="$(detect_role_with 0 0 "$TMP/build-info.json" "$TMP/ambig")"
[[ "$r" == "AMBIGUOUS" ]] || fail "live corpus plus bundle must fail closed (got $r)"
amb_out="$(
  # shellcheck disable=SC1090
  source "$MM"
  MD_MM_LIB="$ROOT/deploy/lib"; MD_MM_DIR="$TMP/ambig"
  MD_MM_BUNDLE_DIR="$TMP/ambig/bundle"; MD_MM_BUILD_INFO="$TMP/build-info.json"
  md_mm_has_live_corpus() { return 0; }
  md_mm_has_bundle() { return 0; }
  md_mm_detect_role 2>&1 || true
)"
grep -q 'Host role is ambiguous' <<<"$amb_out" || fail "ambiguity must be explained to the operator"
grep -q 'HOW TO FIX' <<<"$amb_out" || fail "ambiguity must tell the operator what to do"
pass "2. ambiguous role fails closed with an explanation"

# --------------------------------------------------------------------------
# 3-6. state: creation, atomic update, resume, incompatible version
# --------------------------------------------------------------------------
S="$TMP/state-src"
py state-init --dir "$S" --role source --migration-id mig-1 >/dev/null
[[ -f "$S/state.json" ]] || fail "state.json not created"
[[ "$(py state-get --dir "$S" --key role)" == "source" ]] || fail "role not stored"
pass "3. state creation"

grep -q 'os.replace' "$PY" || fail "state write must be atomic (temp + rename)"
grep -q 'os.fsync' "$PY" || fail "state write must fsync for power-loss safety"
py state-set --dir "$S" "c_cut=abc123"
[[ "$(py state-get --dir "$S" --key c_cut)" == "abc123" ]] || fail "state-set failed"
pass "4. atomic state update"

py state-complete --dir "$S" --phase source_preflight
py state-complete --dir "$S" --phase source_preflight
n="$(py state-get --dir "$S" --key completed_phases | grep -c source_preflight)"
[[ "$n" -eq 1 ]] || fail "completed phase must not duplicate on resume ($n)"
[[ "$(py state-get --dir "$S" --key current_phase)" == "source_preflight" ]] \
  || fail "current phase not recorded"
pass "5. resume after interruption is idempotent"

python3 -c "
import json,sys
p='$S/state.json'
d=json.load(open(p)); d['schema_version']=999
json.dump(d,open(p,'w'))
"
if py state-get --dir "$S" --key role >/dev/null 2>&1; then
  fail "incompatible state version must be refused"
fi
pass "6. incompatible state version refused"

# --------------------------------------------------------------------------
# 7-9. preflight structure and grouped reporting
# --------------------------------------------------------------------------
grep -q 'md_mm_source_preflight' "$MM" || fail "source preflight missing"
for code in MM-SP01 MM-SP02 MM-SP03 MM-SP04; do
  grep -q "$code" "$MM" || fail "source preflight missing check $code"
done
pass "7. source preflight checks git, tree, origin/main and database"

grep -q 'md_mm_target_preflight' "$MM" || fail "target preflight missing"
for code in MM-TP01 MM-TP02 MM-TP03 MM-TP04 MM-TP05 MM-TP07 MM-TP08 MM-TP09 MM-TP10 MM-TP11; do
  grep -q "$code" "$MM" || fail "target preflight missing check $code"
done
grep -q 'C.UTF-8' "$MM" || fail "target preflight must check collation locale"
pass "8. target preflight checks platform, services, permissions, git auth"

# All independent read-only failures reported together, in the 4-field shape.
out="$(
  # shellcheck disable=SC1090
  source "$MM"
  md_mm_pf_reset
  md_mm_pf_add C1 "first thing" "first why" "first fix"
  md_mm_pf_add C2 "second thing" "second why" "second fix"
  md_mm_pf_report 2>&1 || true
)"
echo "$out" | grep -q "first thing" || fail "first preflight failure not reported"
echo "$out" | grep -q "second thing" || fail "second preflight failure not reported"
[[ "$(echo "$out" | grep -c 'WHAT FAILED')" -eq 2 ]] || fail "expected 2 grouped failures"
[[ "$(echo "$out" | grep -c 'RUN AGAIN')" -eq 1 ]] || fail "RUN AGAIN must appear once"
echo "$out" | grep -q 'MIGRATION STOPPED' || fail "missing MIGRATION STOPPED header"
pass "9. all preflight failures reported together"

# Failure shape is exactly four fields.
out="$(
  # shellcheck disable=SC1090
  source "$MM"
  md_mm_fail X-1 "what" "why" "fix" 2>&1 || true
)"
for field in 'WHAT FAILED' 'WHY' 'HOW TO FIX' 'RUN AGAIN'; do
  echo "$out" | grep -q "$field" || fail "failure output missing $field"
done
[[ "$(echo "$out" | grep -cE '^(WHAT FAILED|WHY|HOW TO FIX|RUN AGAIN)')" -eq 4 ]] \
  || fail "failure output must contain exactly four fields"
pass "9b. failure output shape is exactly four fields"

# --------------------------------------------------------------------------
# 10-13. confirmation gates
# --------------------------------------------------------------------------
grep -q 'md_mm_confirm_once FREEZE' "$MM" || fail "FREEZE gate missing"
grep -q 'md_mm_confirm_once ERASE' "$MM" || fail "ERASE gate missing"
grep -q 'md_mm_confirm_once ACCEPT' "$MM" || fail "ACCEPT gate missing"
grep -q 'md_mm_confirm_once SWITCH' "$MM" || fail "SWITCH gate missing"
grep -q 'md_confirm_typed' "$MM" || fail "must reuse existing typed confirmation helper"
# Only the four forward words plus ROLLBACK exist as gates.
words="$(grep -oE 'md_mm_confirm_once [A-Z]+' "$MM" | awk '{print $2}' | sort -u | tr '\n' ' ')"
[[ "$words" == "ACCEPT ERASE FREEZE ROLLBACK SWITCH " ]] \
  || fail "unexpected confirmation words: $words"
pass "10-11. FREEZE and ERASE confirmations required; no extra gates"

# Destructive confirmations are recorded so they are never auto-repeated.
py state-init --dir "$TMP/conf" --role target --migration-id mig-c >/dev/null
if py state-has-confirm --dir "$TMP/conf" --word ERASE; then fail "unconfirmed word reported"; fi
py state-confirm --dir "$TMP/conf" --word ERASE
py state-has-confirm --dir "$TMP/conf" --word ERASE || fail "confirmation not recorded"
pass "11b. destructive confirmation recorded, never auto-repeated"

# Phase order guarantees ACCEPT cannot precede a passing report, nor SWITCH precede ACCEPT.
phase_order() { grep -A 4 'md_mm_run_phases \\' "$MM" | tr -d '\\\n' | tr -s ' '; }
order="$(phase_order)"
echo "$order" | grep -q 'target_report *target_accept *target_switch' \
  || fail "phase order must be report -> accept -> switch (got: $order)"
fn_body md_mm_target_report | grep -q 'return 1' \
  || fail "failed acceptance must stop before ACCEPT"
fn_body md_mm_target_report | grep -q 'rollback_available=yes' \
  || fail "failed acceptance must record rollback availability"
pass "12-13. ACCEPT unavailable on failure; SWITCH ordered after ACCEPT"

# --------------------------------------------------------------------------
# 14-18. bundle manifest, verification, wrong/stale artifacts
# --------------------------------------------------------------------------
B="$TMP/bundle"; mkdir -p "$B"
printf 'PGDMPFAKE-1' > "$B/ai_site_agent.20260804_210000.dump"
printf 'SNAPFAKE-1' > "$B/site_knowledge-1.snapshot"
cat > "$TMP/db-facts.json" <<'JSON'
{"alembic_revision":"0019_x","database_name":"ai_site_agent","sources":5023,
 "chunks":17958,"claims":39,"observations":13,"evidence_links":21,
 "chat_messages":4127,"answer_traces":900,
 "chat_messages_max_created_at":"2026-08-04 20:59:00",
 "answer_traces_max_created_at":"2026-08-04 20:58:00",
 "knowledge_version":26,"memory_version":177,"lc_collate":"C.UTF-8",
 "encoding":"UTF8","server_version":"16.14",
 "feature_flags":{"legacy_doc_type_canonical_enabled":false}}
JSON
cat > "$TMP/qdrant-facts.json" <<'JSON'
{"site_knowledge":{"present":true,"points":18780,"status":"green",
 "vector_size":1024,"distance":"Cosine"},
 "site_knowledge_answer_cache":{"present":true,"points":7,"status":"green",
 "vector_size":1024,"distance":"Cosine"}}
JSON
cat > "$TMP/ollama-facts.json" <<'JSON'
{"digests":{"bge-m3":"7907646426","qwen2.5:3b":"357c53fb65"},"embedding_length":1024}
JSON
cat > "$B/retrieval-baseline.json" <<'JSON'
{"schema_version":1,"query_count":2,"top_k":5,"queries":[
 {"id":"q1","query":"a","top":[{"identity":"aaa","final_score":0.9},
   {"identity":"bbb","final_score":0.8},{"identity":"ccc","final_score":0.7}]},
 {"id":"q2","query":"b","top":[{"identity":"ddd","final_score":0.5},
   {"identity":"eee","final_score":0.4},{"identity":"fff","final_score":0.3}]}]}
JSON

py bundle-manifest \
  --migration-id mig-1 --source-hostname oldhost --operator tester \
  --release 0.8 --c-cut deadbeefdeadbeef \
  --db-facts "$TMP/db-facts.json" --qdrant-facts "$TMP/qdrant-facts.json" \
  --ollama-facts "$TMP/ollama-facts.json" \
  --dump "$B/ai_site_agent.20260804_210000.dump" \
  --baseline "$B/retrieval-baseline.json" \
  --snapshot "site_knowledge=$B/site_knowledge-1.snapshot" \
  --out-json "$B/bundle-manifest.json" --out-md "$B/bundle-manifest.md" >/dev/null
[[ -f "$B/bundle-manifest.json" ]] || fail "bundle manifest not written"
[[ -f "$B/bundle-manifest.md" ]] || fail "human-readable manifest not written"
for key in migration_id c_cut alembic_revision chat_messages answer_traces \
           retrieval_baseline_sha256 feature_flags lc_collate; do
  grep -q "$key" "$B/bundle-manifest.json" || fail "manifest missing $key"
done
python3 -c "
import json; m=json.load(open('$B/bundle-manifest.json'))
assert m['counts']['chat_messages']==4127, 'conversational count missing'
assert m['counts']['answer_traces']==900
assert m['chat_messages_max_created_at'], 'max(created_at) missing'
assert m['qdrant']['points']==18780
assert m['models']['digests']['bge-m3']=='7907646426'
assert len(m['dump']['sha256'])==64
assert m['qdrant_snapshots'][0]['sha256']
"
pass "14. bundle manifest generation includes provenance and conversational state"

py bundle-verify --bundle "$B" --manifest "$B/bundle-manifest.json" --migration-id mig-1 >/dev/null \
  || fail "valid bundle must verify"
pass "15. bundle SHA256 verification"

# 16. stale/replaced dump rejected (same name, different bytes).
cp "$B/ai_site_agent.20260804_210000.dump" "$TMP/orig.dump"
printf 'PGDMPFAKE-STALE' > "$B/ai_site_agent.20260804_210000.dump"
if py bundle-verify --bundle "$B" --manifest "$B/bundle-manifest.json" >/dev/null 2>&1; then
  fail "stale dump must be rejected"
fi
cp "$TMP/orig.dump" "$B/ai_site_agent.20260804_210000.dump"
pass "16. stale dump rejected by checksum"

# 17. wrong snapshot rejected.
cp "$B/site_knowledge-1.snapshot" "$TMP/orig.snap"
printf 'SNAPFAKE-WRONG' > "$B/site_knowledge-1.snapshot"
if py bundle-verify --bundle "$B" --manifest "$B/bundle-manifest.json" >/dev/null 2>&1; then
  fail "wrong snapshot must be rejected"
fi
cp "$TMP/orig.snap" "$B/site_knowledge-1.snapshot"
pass "17. wrong snapshot rejected by checksum"

# 18. dump and snapshot share one migration id; a foreign id is refused.
if py bundle-verify --bundle "$B" --manifest "$B/bundle-manifest.json" \
     --migration-id mig-OTHER >/dev/null 2>&1; then
  fail "mismatched migration id must be refused"
fi
pass "18. dump and snapshot must share one migration id"

# --------------------------------------------------------------------------
# 19. restore flags and safety
# --------------------------------------------------------------------------
grep -q 'pg_restore --exit-on-error --single-transaction' "$MM" \
  || fail "pg_restore must use --exit-on-error --single-transaction"
grep -q 'dropdb --if-exists' "$MM" || fail "restore must recreate the database"
grep -q 'lc-collate=C.UTF-8' "$MM" || fail "recreated database must set collation"
grep -q 'never typed' "$MM" || fail "dump path must be derived from the manifest"
fn_body md_mm_target_restore | grep -q 'recovery' \
  || fail "restore must refuse a recovery database target"
fn_body md_mm_target_restore | grep -q 'bundle-verify' \
  || fail "bundle must be re-verified immediately before destructive work"
pass "19. PostgreSQL restore is atomic, targeted and manifest-derived"

# --------------------------------------------------------------------------
# 20-22. retrieval baseline and parity
# --------------------------------------------------------------------------
grep -q 'baseline-capture' "$MM" || fail "source must capture a retrieval baseline"
grep -q "backend/tests/golden/queries.json" "$MM" \
  || fail "must reuse the existing 30-query golden fixture"
grep -q 'debug.*True' "$PY" || fail "baseline must use debug=true"
grep -q 'bypass_cache' "$PY" || fail "baseline must bypass the cache"
grep -q 'chunk_identity' "$PY" || fail "baseline needs a stable chunk identity"
python3 -c "
import sys; sys.path.insert(0,'$ROOT/deploy/lib')
from migrate_machine import chunk_identity
a=chunk_identity({'url':'u','heading':'h','text_preview':'t'})
b=chunk_identity({'url':'u','heading':'h','text_preview':'t'})
c=chunk_identity({'url':'u','heading':'other','text_preview':'t'})
assert a==b, 'identity must be stable'
assert a!=c, 'identity must distinguish chunks'
"
[[ "$(python3 -c "
import sys; sys.path.insert(0,'$ROOT/deploy/lib')
import migrate_machine as m
print(m.PARITY_TOP3_MIN_MATCHES, m.PARITY_SCORE_TOLERANCE, m.PARITY_RANK1_REQUIRED_RATIO)")" \
  == "28 0.01 1.0" ]] || fail "parity thresholds must not be loosened"
pass "20. retrieval baseline capture uses the golden fixture and stable identity"

cp "$B/retrieval-baseline.json" "$TMP/actual-good.json"
py baseline-compare --baseline "$B/retrieval-baseline.json" \
  --actual "$TMP/actual-good.json" --out "$TMP/parity-good.json" >/dev/null \
  || fail "identical retrieval must pass parity"
python3 -c "
import json; r=json.load(open('$TMP/parity-good.json'))
assert r['passed'] is True
assert r['rank1_matches']==r['total']
"
pass "21. retrieval parity pass fixture"

python3 -c "
import json
d=json.load(open('$B/retrieval-baseline.json'))
d['queries'][0]['top'][0]['identity']='zzz'   # rank-1 changed
json.dump(d,open('$TMP/actual-bad.json','w'))
"
if py baseline-compare --baseline "$B/retrieval-baseline.json" \
     --actual "$TMP/actual-bad.json" --out "$TMP/parity-bad.json" >/dev/null 2>&1; then
  fail "degraded retrieval must fail parity"
fi
python3 -c "
import json; r=json.load(open('$TMP/parity-bad.json'))
assert r['passed'] is False, 'parity must fail on rank-1 change'
"
# Score drift beyond tolerance also fails.
python3 -c "
import json
d=json.load(open('$B/retrieval-baseline.json'))
d['queries'][0]['top'][0]['final_score']=0.5   # was 0.9
json.dump(d,open('$TMP/actual-drift.json','w'))
"
if py baseline-compare --baseline "$B/retrieval-baseline.json" \
     --actual "$TMP/actual-drift.json" --out "$TMP/parity-drift.json" >/dev/null 2>&1; then
  fail "score drift beyond tolerance must fail parity"
fi
pass "22. retrieval parity failure fixture (rank-1 and score drift)"

# --------------------------------------------------------------------------
# 23-25. digest gate, conditional migrate release, C_cut movement
# --------------------------------------------------------------------------
fn_body md_mm_target_gate | grep -q 'bge-m3' \
  || fail "gate must compare the bge-m3 digest"
fn_body md_mm_target_gate | grep -q 'MM-TG04' \
  || fail "digest mismatch needs a stable error code"
# The digest gate must precede deploy in the phase order.
ord="$(phase_order)"
[[ "$ord" == *"target_gate"*"target_deploy"* ]] || fail "digest gate must block cutover"
pass "23. model digest mismatch blocks cutover"

fn_body md_mm_target_schema | grep -q 'migrate release --yes' \
  || fail "schema phase must delegate to migrate release"
fn_body md_mm_target_schema | grep -q 'nothing to apply' \
  || fail "schema phase must no-op when revisions already match"
pass "24. migrate release runs only when the repository head is ahead"

fn_body md_mm_target_deploy | grep -q 'origin/main has moved' \
  || fail "deploy must refuse when origin/main moved"
fn_body md_mm_target_deploy | grep -q 'deploy_guard_origin_main_hash' \
  || fail "deploy must compare against origin/main via the existing guard"
pass "25. C_cut movement blocks deploy"

# --------------------------------------------------------------------------
# 26-28. reuse of existing commands, no duplicated logic
# --------------------------------------------------------------------------
grep -q 'md_mm_run_cli deploy full' "$MM" || fail "must reuse deploy full"
grep -q 'md_mm_run_cli backup db' "$MM" || fail "must reuse backup db"
grep -q 'md_mm_run_cli health' "$MM" || fail "must reuse health"
grep -q 'SMOKE_CHAT=1 md_mm_run_cli smoke' "$MM" || fail "must reuse smoke with chat enabled"
grep -q 'md_mm_run_cli verify-release' "$MM" || fail "must reuse verify-release"
pass "26-28. deploy full / backup db / health / smoke / verify-release reused"

# No reimplementation of the delegated logic.
if grep -qE '^[^#]*\bpg_dump\b' "$MM"; then fail "must not reimplement pg_dump (use backup db)"; fi
if grep -qE '^[^#]*alembic (upgrade|downgrade)' "$MM"; then
  fail "must not run alembic directly (use migrate release)"
fi
if grep -qE '^[^#]*rsync ' "$MM"; then fail "must not reimplement code sync (use deploy full)"; fi
pass "28b. no duplicated backup, migration or deploy logic"

# --------------------------------------------------------------------------
# 29. rollback
# --------------------------------------------------------------------------
grep -q 'md_mm_rollback' "$MM" || fail "rollback missing"
R="$(fn_body md_mm_rollback)"
grep -q 'stop --module backend' <<<"$R" || fail "rollback must stop the target backend"
grep -q 'systemctl start ai-agent-backend' <<<"$R" || fail "rollback must restore source authority"
grep -q 'DISCARDED' <<<"$R" || fail "rollback must state that target writes are discarded"
grep -q 'expected drift, NOT a rollback failure' <<<"$R" \
  || fail "rollback must not treat identity drift as failure"
grep -q 'never modified by a rollback' <<<"$R" \
  || fail "rollback must never write back into the source"
if grep -qE '^[^#]*pg_restore' <<<"$R"; then fail "rollback must not restore data into the source"; fi
grep -q 'rollback-report.md' "$MM" || fail "rollback must write a report"
pass "29. rollback returns authority to the source without data merge"

# --------------------------------------------------------------------------
# 30. secrets never appear in reports
# --------------------------------------------------------------------------
grep -q 'redact_url' "$PY" || fail "helper must redact database URLs"
python3 -c "
import sys; sys.path.insert(0,'$ROOT/deploy/lib')
from migrate_machine import redact_url
r=redact_url('postgresql+psycopg://ai_agent:s3cret-pass@localhost:5432/ai_site_agent')
assert 's3cret-pass' not in r, 'password leaked'
assert '***' in r and 'ai_site_agent' in r
"
for f in "$B/bundle-manifest.json" "$B/bundle-manifest.md"; do
  grep -qiE 'password|secret|PGPASSWORD' "$f" && fail "secret-like key in $f"
done
python3 -c "
import json; m=json.load(open('$B/bundle-manifest.json'))
blob=json.dumps(m).lower()
for bad in ('password','secret','token','pgpassword'):
    assert bad not in blob, bad
"
pass "30. secrets never appear in reports"

# --------------------------------------------------------------------------
# 31. no Qdrant clear / reindex path
# --------------------------------------------------------------------------
if grep -qE '^[^#]*(clear-qdrant|CLEAR_QDRANT=1|reindex|--clear-qdrant)' "$MM"; then
  fail "migration must never clear Qdrant or reindex"
fi
grep -q 'never clear the collection or re-index' "$MM" \
  || fail "must state that clearing/reindexing is not a fix"
grep -q 'snapshots/upload' "$MM" || fail "Qdrant must be restored via the native snapshot API"
pass "31. no Qdrant clear or reindex path exists"

# --------------------------------------------------------------------------
# 32. public CLI surface
# --------------------------------------------------------------------------
help_out="$(bash "$MD" help 2>&1 || true)"
echo "$help_out" | grep -q 'migrate-machine' || fail "help missing migrate-machine"
# No public phase/role subcommands or flags.
for forbidden in 'migrate-machine source' 'migrate-machine target' 'migrate-machine preflight' \
                 'migrate-machine capture' 'migrate-machine restore' 'migrate-machine accept' \
                 '--source' '--target'; do
  if echo "$help_out" | grep -q -- "$forbidden"; then
    fail "help must not expose '$forbidden'"
  fi
done
grep -q 'migrate-machine)' "$CLI" || fail "cli must dispatch migrate-machine"
grep -q 'md_migrate_machine' "$CLI" || fail "cli must call md_migrate_machine"
# Arguments are refused: the tool decides the phase, not the operator.
if bash "$MD" migrate-machine somephase >/dev/null 2>&1; then
  fail "migrate-machine must refuse arguments"
fi
arg_out="$(bash "$MD" migrate-machine somephase 2>&1 || true)"
grep -q 'does not take arguments' <<<"$arg_out" \
  || fail "argument refusal must explain itself"
pass "32. migrate-machine is the only public migration command, with no options"

# --------------------------------------------------------------------------
# acceptance report: expected/actual/PASS-FAIL, and FAIL blocks acceptance
# --------------------------------------------------------------------------
cat > "$TMP/actual-state.json" <<JSON
{"db": $(cat "$TMP/db-facts.json"),
 "qdrant": $(cat "$TMP/qdrant-facts.json"),
 "ollama": $(cat "$TMP/ollama-facts.json"),
 "deployed_commit":"deadbeefdeadbeef","release":"0.8",
 "health":"pass","smoke":"pass","verify_release":"pass"}
JSON
py accept-report --manifest "$B/bundle-manifest.json" --actual "$TMP/actual-state.json" \
  --parity "$TMP/parity-good.json" --out-json "$TMP/acc.json" --out-md "$TMP/acc.md" \
  > "$TMP/acc.txt" || fail "matching state must produce PASS"
grep -q 'ACCEPTANCE —' "$TMP/acc.txt" || fail "report header missing"
grep -qE 'CRITERION +EXPECTED +ACTUAL +RESULT' "$TMP/acc.txt" || fail "report columns missing"
grep -q 'RESULT: PASS' "$TMP/acc.txt" || fail "expected overall PASS"
grep -q 'retrieval rank-1' "$TMP/acc.txt" || fail "retrieval parity must be a criterion"
grep -q 'chat_messages' "$TMP/acc.txt" || fail "conversational count must be a criterion"
pass "33. acceptance report is expected/actual/PASS-FAIL and evaluated by the tool"

python3 -c "
import json
d=json.load(open('$TMP/actual-state.json'))
d['db']['sources']=1   # wrong corpus
json.dump(d,open('$TMP/actual-bad-state.json','w'))
"
if py accept-report --manifest "$B/bundle-manifest.json" --actual "$TMP/actual-bad-state.json" \
     --parity "$TMP/parity-good.json" --out-json "$TMP/acc2.json" --out-md "$TMP/acc2.md" \
     >/dev/null 2>&1; then
  fail "mismatched state must produce FAIL"
fi
grep -q 'RESULT: FAIL' "$TMP/acc2.md" || fail "expected overall FAIL"
pass "34. a single mismatch fails acceptance"

# --------------------------------------------------------------------------
# runtime product code untouched
# --------------------------------------------------------------------------
for f in "$MM" "$PY"; do
  if grep -qE '^[^#]*(backend/app/|dashboard/src/)' "$f"; then
    fail "migration orchestrator must not reference runtime product code: $f"
  fi
done
pass "35. orchestrator does not touch runtime product code"

# --------------------------------------------------------------------------
# the tool always answers "what do I do now?"
# --------------------------------------------------------------------------
grep -q 'TARGET READY' "$MM" || fail "run 1 must end with TARGET READY"
grep -q 'BUNDLE DELIVERED' "$MM" || fail "run 2 must end with BUNDLE DELIVERED"
grep -q 'MIGRATION COMPLETE' "$MM" || fail "run 3 must end with a completion message"
[[ "$(grep -c 'Next action: run the same command' "$MM")" -ge 2 ]] \
  || fail "each hand-off must name the next host"
# Every terminal message points back at the one command.
[[ "$(grep -c "MD_MM_CMD" "$MM")" -ge 5 ]] || fail "guidance must always cite the one command"
grep -q "MD_MM_CMD='bash deploy/manage_deploy.sh migrate-machine'" "$MM" \
  || fail "the cited command must be the single public entry point"
pass "36. every stop states the next action and the one command to run"

echo ""
echo "OK: migrate-machine regression passed"
