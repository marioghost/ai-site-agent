#!/usr/bin/env bash
# Backend unit tests excluding golden parity (release-check step 1).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="$ROOT/backend"
VENV="${BACKEND}/.venv"

if [[ ! -x "$VENV/bin/pytest" ]]; then
  echo "ERROR: backend venv missing. Run: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

cd "$BACKEND"

echo "==> Backend unit tests (excluding golden parity)"
"$VENV/bin/pytest" \
  tests/test_broad_query_handling.py \
  tests/test_retrieval_hybrid.py \
  tests/test_legacy_guards.py \
  tests/test_document_first_retrieval.py \
  tests/test_boilerplate_retrieval.py \
  tests/test_chat_executive_routing.py \
  tests/test_chat_stream_executive_routing.py \
  tests/test_executive_service.py \
  tests/test_chat_dispatch_logging.py \
  tests/test_retrieval_pipeline_v2.py \
  tests/test_semantic_diagnostics_schema.py \
  tests/test_chat_response_builder.py \
  tests/test_knowledge_profile_preset_deprecation.py \
  tests/test_memory_version_schema.py \
  tests/test_memory_version_service.py \
  tests/test_memory_version_bump_api.py \
  tests/test_cache_namespace_v2.py \
  tests/test_cache_namespace_v2_invariants.py \
  tests/test_operational_metrics.py \
  tests/test_build_info.py \
  tests/test_epistemic_memory_schema.py \
  tests/test_epistemic_memory_service.py \
  tests/test_claim_extraction_from_si.py \
  tests/test_epistemic_memory_shadow_write.py \
  tests/test_epistemic_shadow_memory_version_bump.py \
  tests/test_epistemic_memory_roundtrip.py \
  tests/test_tension_surfacing_service.py \
  tests/test_caching.py \
  -m "unit and not benchmark" -q "$@"

echo "OK: backend unit tests passed"
