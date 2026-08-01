"""RFC-100 Step 006 — golden chat parity CI smoke gate.

Unit tests (default CI):
  Deterministic fixture RagResults — no PostgreSQL, no LLM, no Qdrant.

Integration tests (optional):
  Require POSTGRES_TEST_URL and GOLDEN_CHAT_LIVE=1 — hits /api/chat with mocks
  at the HTTP boundary. Live LLM is never required for the smoke gate.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from golden.parity_runner import (
    GoldenInvariantViolation,
    build_chat_response,
    build_fixture_rag_result,
    compare_structural_parity,
    load_golden_smoke,
    validate_golden_invariants,
)

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")
GOLDEN_CHAT_LIVE = os.environ.get("GOLDEN_CHAT_LIVE") == "1"


def _smoke_query_ids() -> list[str]:
    return [q["id"] for q in load_golden_smoke()["queries"]]


@pytest.fixture(scope="module")
def golden_smoke() -> dict:
    return load_golden_smoke()


def _run_dispatch_path(
    monkeypatch,
    *,
    executive: bool,
    item: dict,
    golden_data: dict,
):
    from app.api.chat import _dispatch_non_stream_answer

    fixture = build_fixture_rag_result(golden_data, item)
    rag_called = {"n": 0}
    executive_called = {"n": 0}

    class _FakeRag:
        def answer(self, *args, **kwargs):
            rag_called["n"] += 1
            return fixture

    class _FakeExecutive:
        def answer(self, *args, **kwargs):
            executive_called["n"] += 1
            return fixture

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: executive)
    # Legacy path under test is RagService (not Reasoning); Step 063 defaults Reasoning ON.
    monkeypatch.setattr("app.api.chat.reasoning_service_enabled", lambda: False)
    monkeypatch.setattr("app.api.chat.RagService", lambda db, settings: _FakeRag())
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )

    result = _dispatch_non_stream_answer(
        MagicMock(),
        MagicMock(),
        item["query"],
        "golden-session",
        request_id=f"golden-{item['id']}",
    )

    if executive:
        assert executive_called["n"] == 1, f"{item['id']}: expected Executive path"
        assert rag_called["n"] == 0, f"{item['id']}: RagService must not run when flag ON"
    else:
        assert rag_called["n"] == 1, f"{item['id']}: expected legacy RagService path"
        assert executive_called["n"] == 0, f"{item['id']}: Executive must not run when flag OFF"

    return result


@pytest.mark.unit
@pytest.mark.parametrize("query_id", _smoke_query_ids())
def test_golden_legacy_executive_parity_per_query(monkeypatch, golden_smoke, query_id):
    """Each smoke query: legacy vs executive structural parity (mocked RAG)."""
    item = next(q for q in golden_smoke["queries"] if q["id"] == query_id)

    legacy_result = _run_dispatch_path(
        monkeypatch, executive=False, item=item, golden_data=golden_smoke
    )
    executive_result = _run_dispatch_path(
        monkeypatch, executive=True, item=item, golden_data=golden_smoke
    )

    legacy_response = build_chat_response(legacy_result)
    executive_response = build_chat_response(executive_result)

    validate_golden_invariants(legacy_response, item, golden_smoke)
    validate_golden_invariants(executive_response, item, golden_smoke)
    validate_golden_invariants(
        legacy_response, item, golden_smoke, include_diagnostics=True
    )

    compare_structural_parity(
        legacy_response, executive_response, query_id=item["id"]
    )


@pytest.mark.unit
def test_golden_smoke_suite_all_queries(golden_smoke, monkeypatch):
    """Iterate all smoke queries in one test — fast CI summary."""
    assert len(golden_smoke["queries"]) == len(_smoke_query_ids())
    failures: list[str] = []

    for item in golden_smoke["queries"]:
        try:
            legacy_result = _run_dispatch_path(
                monkeypatch, executive=False, item=item, golden_data=golden_smoke
            )
            executive_result = _run_dispatch_path(
                monkeypatch, executive=True, item=item, golden_data=golden_smoke
            )
            legacy_response = build_chat_response(legacy_result)
            executive_response = build_chat_response(executive_result)
            validate_golden_invariants(legacy_response, item, golden_smoke)
            validate_golden_invariants(executive_response, item, golden_smoke)
            compare_structural_parity(
                legacy_response, executive_response, query_id=item["id"]
            )
        except GoldenInvariantViolation as exc:
            failures.append(str(exc))

    assert not failures, "Golden failures:\n" + "\n".join(failures)


@pytest.mark.unit
def test_golden_invariant_violation_empty_answer_detected(golden_smoke):
    item = golden_smoke["queries"][0]
    bad = build_chat_response(build_fixture_rag_result(golden_smoke, item))
    bad["answer"] = "   "
    with pytest.raises(GoldenInvariantViolation, match="empty_answer"):
        validate_golden_invariants(bad, item, golden_smoke)


@pytest.mark.integration
@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="requires POSTGRES_TEST_URL (PostgreSQL test database)",
)
@pytest.mark.skipif(
    not GOLDEN_CHAT_LIVE,
    reason="requires GOLDEN_CHAT_LIVE=1 for HTTP golden integration (optional)",
)
def test_golden_http_chat_integration(client, auth_headers, golden_smoke, monkeypatch):
    """Optional HTTP /api/chat smoke — PostgreSQL required, no live LLM.

    Set GOLDEN_CHAT_LIVE=1 to enable. Full live-LLM golden runs are ops/nightly
    (RFC-100 Step 012), not PR CI.
    """
    class _FakeRag:
        def answer(self, message, session_id, **kwargs):
            item = next(q for q in golden_smoke["queries"] if q["query"] == message)
            return build_fixture_rag_result(golden_smoke, item)

    monkeypatch.setattr("app.api.chat.RagService", lambda db, settings: _FakeRag())
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService",
        lambda db, settings: _FakeRag(),
    )

    sid = client.post("/api/chat/sessions", json={}, headers=auth_headers).json()[
        "session_id"
    ]

    for item in golden_smoke["queries"]:
        for executive in (False, True):
            monkeypatch.setattr(
                "app.api.chat.knowledge_os_executive_enabled", lambda e=executive: e
            )
            monkeypatch.setattr(
                "app.api.chat.reasoning_service_enabled", lambda: False
            )
            res = client.post(
                "/api/chat",
                json={
                    "message": item["query"],
                    "session_id": sid,
                    "debug": True,
                },
                headers=auth_headers,
            )
            assert res.status_code == 200, f"{item['id']} executive={executive}"
            body = res.json()
            validate_golden_invariants(body, item, golden_smoke)
