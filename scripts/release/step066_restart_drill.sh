#!/usr/bin/env bash
# RFC-100 Step 066 — service restart drill (designated /opt staging).
# Engineering Package §7–§8: restart backend under light traffic; prove health + tip.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE="${STAGING_BASE_URL:-http://127.0.0.1:8000}"
OUT_DIR="$ROOT/docs/releases"
REPORT="$OUT_DIR/1.0-step-066-restart-report.json"
TIP_EXPECTED="${STEP066_TIP_SHA:-a41198f28f59c2d22c78e63f0afec9448ca8fe0c}"

mkdir -p "$OUT_DIR"

write_report() {
  local verdict="$1" detail="$2" tip_b="${3:-}" tip_a="${4:-}" health="${5:-false}"
  python3 - <<PY
import json
from datetime import datetime, timezone
report={
  "step":"066",
  "drill":"service_restart",
  "finished_at": datetime.now(timezone.utc).isoformat(),
  "tip_expected": "$TIP_EXPECTED",
  "tip_before": """$tip_b""",
  "tip_after": """$tip_a""",
  "health_ok": $health,
  "verdict": "$verdict",
  "detail": """$detail""",
  "command": "sudo bash deploy/manage_deploy.sh --action restart --module backend",
}
open("$REPORT","w",encoding="utf-8").write(json.dumps(report,indent=2)+"\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if "$verdict"=="PASS" else 1)
PY
}

if ! before="$(curl -sfS --max-time 30 "$BASE/api/build")"; then
  write_report "FAIL" "pre-restart /api/build unreachable" "" "" false
fi

echo "==> Step 066 restart drill: before tip=$(echo "$before" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("git_commit"))')"

if ! sudo -n true 2>/dev/null; then
  write_report "FAIL" "sudo non-interactive unavailable; operator TTY required for One Command restart" \
    "$(echo "$before" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("git_commit",""))')" "" false
fi

# One Command / existing ops path — backend module restart
sudo bash "$ROOT/deploy/manage_deploy.sh" --action restart --module backend

ok=0
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sfS --max-time 10 "$BASE/api/health" >/dev/null; then ok=1; break; fi
  sleep 2
done
if [[ "$ok" != "1" ]]; then
  write_report "FAIL" "health failed after restart" \
    "$(echo "$before" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("git_commit",""))')" "" false
fi

after="$(curl -sfS --max-time 30 "$BASE/api/build")"
tip_b="$(echo "$before" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("git_commit",""))')"
tip_a="$(echo "$after" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("git_commit",""))')"
verdict="PASS"
if [[ "$tip_a" != *"${TIP_EXPECTED:0:7}"* && "$TIP_EXPECTED" != *"${tip_a:0:7}"* ]]; then
  verdict="FAIL"
fi
write_report "$verdict" "restart completed via manage_deploy" "$tip_b" "$tip_a" true
