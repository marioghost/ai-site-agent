#!/usr/bin/env bash
# RFC-100 Step 066 — cleanup harness-tagged Ask sessions (prefix step066-load-).
# Best-effort; does not mutate Settings/flags/index.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREFIX="${STEP066_SESSION_PREFIX:-step066-load-}"
# Prefer SQL via /opt venv if available
PY="${ROOT}/backend/.venv/bin/python"
if [[ -x /opt/ai-site-agent/backend/.venv/bin/python ]]; then
  PY=/opt/ai-site-agent/backend/.venv/bin/python
fi
"$PY" - <<PY
import os, sys
sys.path.insert(0, "${ROOT}/backend")
os.chdir("${ROOT}/backend")
try:
    from app.core.database import SessionLocal
    from app.models.chat_session import ChatSession
except Exception as exc:
    print(f"SKIP cleanup (import): {exc}")
    raise SystemExit(0)
prefix = "${PREFIX}"
db = SessionLocal()
try:
    q = db.query(ChatSession).filter(ChatSession.session_id.like(prefix + "%"))
    n = q.count()
    q.delete(synchronize_session=False)
    db.commit()
    print(f"deleted_sessions={n} prefix={prefix}")
finally:
    db.close()
PY
