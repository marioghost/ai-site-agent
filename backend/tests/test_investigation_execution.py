"""RFC-100 Step 060 — investigation execution (unit)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.epistemic_maintenance import (
    ACTION_SEEK_ADJUDICATION,
    ACTION_SEEK_CORROBORATION,
    InvestigationPlan,
)
from app.services.epistemic_memory.types import EvidenceLinkView, ObservationRefView
from app.services.executive.investigation_execution import (
    execute_selected_investigations,
)
from app.services.executive.investigation_target import resolve_investigation_target
from app.services.executive.investigation_types import (
    REASON_CONTENT_UNCHANGED,
    REASON_FETCH_DISALLOWED,
    REASON_FETCH_FAILED,
    REASON_INDEX_FAILED,
    REASON_INDEXING_BUSY,
    REASON_INTERRUPTED,
    REASON_MEMORY_SHADOW_WRITE_FAILED,
    REASON_PARSE_FAILED,
    REASON_SI_FAILED,
    REASON_SOURCE_MISSING,
    REASON_SOURCE_URL_UNAVAILABLE,
    REASON_TARGET_AMBIGUOUS,
    REASON_TARGET_UNRESOLVED,
    REASON_UNSUPPORTED_ACTION,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCEEDED,
)
from app.services.executive.maintenance_cycle_invoker import MaintenanceCycleInvoker
from app.services.executive.maintenance_types import MaintenanceCycleResult
from app.services.index_integrate.types import (
    REASON_CONTENT_UNCHANGED as COMPOSE_CONTENT_UNCHANGED,
    REASON_FETCH_FAILED as COMPOSE_FETCH_FAILED,
    REASON_INDEX_FAILED as COMPOSE_INDEX_FAILED,
    REASON_MEMORY_SHADOW_WRITE_FAILED as COMPOSE_MEMORY_FAILED,
    REASON_PARSE_FAILED as COMPOSE_PARSE_FAILED,
    REASON_SI_FAILED as COMPOSE_SI_FAILED,
    STAGE_INDEXING,
    STAGE_MEMORY_INTEGRATION,
    STAGE_NONE,
    STAGE_SOURCE_INTELLIGENCE,
    STATUS_FAILED as COMPOSE_FAILED,
    STATUS_SKIPPED as COMPOSE_SKIPPED,
    STATUS_SUCCEEDED as COMPOSE_SUCCEEDED,
    IndexIntegrateResult,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _plan(
    plan_id: str = "p1",
    *,
    action: str = ACTION_SEEK_CORROBORATION,
    claim_ids: tuple[int, ...] = (1,),
    observation_ref_ids: tuple[int, ...] = (10,),
) -> InvestigationPlan:
    return InvestigationPlan(
        plan_id=plan_id,
        tension_type="support_deficit",
        claim_ids=claim_ids,
        observation_ref_ids=observation_ref_ids,
        evidence_link_ids=(),
        action=action,
        priority=1.0,
        rationale="fixture",
    )


def _obs(obs_id: int, source_id: int | None) -> ObservationRefView:
    return ObservationRefView(
        id=obs_id,
        source_id=source_id,
        chunk_id=None,
        observation_key=f"k{obs_id}",
        content_hash="h",
        excerpt=None,
        observed_at=_NOW,
        provenance_kind="test",
        provenance_ref=None,
        extraction_version=None,
        created_at=_NOW,
    )


def _link(claim_id: int, obs_id: int) -> EvidenceLinkView:
    return EvidenceLinkView(
        id=1,
        claim_id=claim_id,
        observation_ref_id=obs_id,
        role="support",
        provenance_kind="test",
        provenance_ref=None,
        link_confidence=None,
        created_at=_NOW,
    )


def _settings(*, allowed: str = "[]", deny: str = "[]") -> MagicMock:
    s = MagicMock()
    s.allowed_domains_json = allowed
    s.deny_url_patterns_json = deny
    return s


def _source(sid: int = 5, url: str = "https://example.com/page") -> MagicMock:
    src = MagicMock()
    src.id = sid
    src.url = url
    return src


def _compose_ok() -> IndexIntegrateResult:
    return IndexIntegrateResult(
        status=COMPOSE_SUCCEEDED,
        completed_stage=STAGE_MEMORY_INTEGRATION,
        failed_stage=None,
        outcome_reason=None,
        indexing_summary="indexed: 3 chunks",
        source_intelligence_summary="source_intelligence_ok",
        memory_summary="memory_integration_ok",
    )


def _compose_failed(reason: str, *, indexing_summary: str = "indexing_failed") -> IndexIntegrateResult:
    failed_stage = STAGE_INDEXING
    completed = STAGE_NONE
    si_summary = None
    mem_summary = None
    if reason == COMPOSE_SI_FAILED:
        failed_stage = STAGE_SOURCE_INTELLIGENCE
        completed = STAGE_INDEXING
        si_summary = "RuntimeError"
    elif reason == COMPOSE_MEMORY_FAILED:
        failed_stage = STAGE_MEMORY_INTEGRATION
        completed = STAGE_SOURCE_INTELLIGENCE
        si_summary = "source_intelligence_ok"
        mem_summary = "RuntimeError"
    return IndexIntegrateResult(
        status=COMPOSE_FAILED,
        completed_stage=completed,
        failed_stage=failed_stage,
        outcome_reason=reason,
        indexing_summary=indexing_summary,
        source_intelligence_summary=si_summary,
        memory_summary=mem_summary,
    )


def test_seek_corroboration_maps_to_fetch() -> None:
    src = _source()
    index = MagicMock(return_value=_compose_ok())
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(action=ACTION_SEEK_CORROBORATION),),
            _settings(),
            index_source=index,
            is_indexing_busy=lambda: False,
        )
    assert result.succeeded == 1
    index.assert_called_once_with(src)


def test_seek_adjudication_maps_to_fetch() -> None:
    src = _source()
    index = MagicMock(return_value=_compose_ok())
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(action=ACTION_SEEK_ADJUDICATION),),
            _settings(),
            index_source=index,
            is_indexing_busy=lambda: False,
        )
    assert result.plan_results[0].status == STATUS_SUCCEEDED
    index.assert_called_once()


def test_unsupported_action() -> None:
    plan = _plan(action="wait")
    result = execute_selected_investigations(
        MagicMock(), (plan,), _settings(), index_source=MagicMock()
    )
    assert result.plan_results[0].reason == REASON_UNSUPPORTED_ACTION
    assert result.skipped == 1


def test_target_unresolved() -> None:
    memory = MagicMock()
    memory.get_observation_ref.return_value = _obs(10, None)
    memory.list_evidence_links_for_claim.return_value = ([], 0)
    res = resolve_investigation_target(
        MagicMock(), _plan(observation_ref_ids=(10,), claim_ids=()), _settings(), memory=memory
    )
    assert res.reason == REASON_TARGET_UNRESOLVED


def test_target_ambiguous() -> None:
    memory = MagicMock()
    memory.get_observation_ref.side_effect = lambda **kw: _obs(
        kw["observation_ref_id"], {10: 1, 11: 2}[kw["observation_ref_id"]]
    )
    res = resolve_investigation_target(
        MagicMock(),
        _plan(observation_ref_ids=(10, 11)),
        _settings(),
        memory=memory,
    )
    assert res.reason == REASON_TARGET_AMBIGUOUS


def test_source_missing() -> None:
    memory = MagicMock()
    memory.get_observation_ref.return_value = _obs(10, 99)
    with patch(
        "app.services.executive.investigation_target.SourceRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = None
        res = resolve_investigation_target(
            MagicMock(), _plan(), _settings(), memory=memory
        )
    assert res.reason == REASON_SOURCE_MISSING


def test_source_url_unavailable() -> None:
    memory = MagicMock()
    memory.get_observation_ref.return_value = _obs(10, 5)
    src = _source(url="  ")
    with patch(
        "app.services.executive.investigation_target.SourceRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = src
        res = resolve_investigation_target(
            MagicMock(), _plan(), _settings(), memory=memory
        )
    assert res.reason == REASON_SOURCE_URL_UNAVAILABLE


def test_fetch_disallowed() -> None:
    memory = MagicMock()
    memory.get_observation_ref.return_value = _obs(10, 5)
    src = _source(url="https://evil.example/x")
    with patch(
        "app.services.executive.investigation_target.SourceRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = src
        res = resolve_investigation_target(
            MagicMock(),
            _plan(),
            _settings(allowed='["good.example"]'),
            memory=memory,
        )
    assert res.reason == REASON_FETCH_DISALLOWED


def test_indexing_busy() -> None:
    src = _source()
    index = MagicMock()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=index,
            is_indexing_busy=lambda: True,
        )
    assert result.plan_results[0].reason == REASON_INDEXING_BUSY
    index.assert_not_called()


def test_exactly_one_dispatch_per_resolved_plan() -> None:
    src = _source()
    index = MagicMock(return_value=_compose_ok())
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        execute_selected_investigations(
            MagicMock(),
            (_plan("a"), _plan("b")),
            _settings(),
            index_source=index,
            is_indexing_busy=lambda: False,
        )
    assert index.call_count == 2


def test_preserves_selected_plan_order() -> None:
    src = _source()
    seen: list[str] = []

    plans = (_plan("first"), _plan("second"), _plan("third"))

    def resolve(db, plan, settings, **kwargs):
        seen.append(plan.plan_id)
        return SimpleNamespace(source=src, reason=None)

    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        side_effect=resolve,
    ):
        result = execute_selected_investigations(
            MagicMock(),
            plans,
            _settings(),
            index_source=lambda _s: _compose_ok(),
            is_indexing_busy=lambda: False,
        )
    assert seen == ["first", "second", "third"]
    assert [r.plan_id for r in result.plan_results] == ["first", "second", "third"]


def test_does_not_call_step_058_rank() -> None:
    rank = MagicMock()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=None, reason=REASON_TARGET_UNRESOLVED),
    ):
        execute_selected_investigations(
            MagicMock(), (_plan(),), _settings(), index_source=MagicMock()
        )
    rank.rank.assert_not_called()


def test_does_not_reselect_or_rerank() -> None:
    """Input tuple is consumed as-is; no sorting by priority."""
    src = _source()
    high = InvestigationPlan(
        plan_id="high",
        tension_type="conflict",
        claim_ids=(1,),
        observation_ref_ids=(10,),
        evidence_link_ids=(),
        action=ACTION_SEEK_ADJUDICATION,
        priority=99.0,
        rationale="r",
    )
    low = InvestigationPlan(
        plan_id="low",
        tension_type="support_deficit",
        claim_ids=(2,),
        observation_ref_ids=(11,),
        evidence_link_ids=(),
        action=ACTION_SEEK_CORROBORATION,
        priority=0.1,
        rationale="r",
    )
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (low, high),
            _settings(),
            index_source=MagicMock(return_value=_compose_ok()),
            is_indexing_busy=lambda: False,
        )
    assert [r.plan_id for r in result.plan_results] == ["low", "high"]


def test_no_full_site_reindex_all_path() -> None:
    src = _source()
    index = MagicMock(return_value=_compose_ok())
    with (
        patch(
            "app.services.executive.investigation_execution.resolve_investigation_target",
            return_value=SimpleNamespace(source=src, reason=None),
        ),
        patch("app.services.indexing_worker_service.indexing_worker") as worker,
    ):
        execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=index,
            is_indexing_busy=lambda: False,
        )
        worker.start.assert_not_called()


def test_content_unchanged_skipped() -> None:
    src = _source()
    outcome = IndexIntegrateResult(
        status=COMPOSE_SKIPPED,
        completed_stage=STAGE_NONE,
        failed_stage=STAGE_INDEXING,
        outcome_reason=COMPOSE_CONTENT_UNCHANGED,
        indexing_summary="skipped: unchanged",
        source_intelligence_summary=None,
        memory_summary=None,
    )
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=lambda _s: outcome,
            is_indexing_busy=lambda: False,
        )
    assert result.plan_results[0].status == STATUS_SKIPPED
    assert result.plan_results[0].reason == REASON_CONTENT_UNCHANGED


def test_fetch_failed() -> None:
    src = _source()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=lambda _s: _compose_failed(
                COMPOSE_FETCH_FAILED, indexing_summary="error: Fetch failed: timeout"
            ),
            is_indexing_busy=lambda: False,
        )
    assert result.plan_results[0].reason == REASON_FETCH_FAILED


def test_parse_failed() -> None:
    src = _source()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=lambda _s: _compose_failed(
                COMPOSE_PARSE_FAILED, indexing_summary="error: Extraction failed"
            ),
            is_indexing_busy=lambda: False,
        )
    assert result.plan_results[0].reason == REASON_PARSE_FAILED


def test_index_failed() -> None:
    src = _source()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=lambda _s: _compose_failed(
                COMPOSE_INDEX_FAILED, indexing_summary="error: Qdrant upsert failed"
            ),
            is_indexing_busy=lambda: False,
        )
    assert result.plan_results[0].reason == REASON_INDEX_FAILED


def test_si_failed() -> None:
    src = _source()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=lambda _s: _compose_failed(COMPOSE_SI_FAILED),
            is_indexing_busy=lambda: False,
        )
    assert result.plan_results[0].reason == REASON_SI_FAILED
    assert result.plan_results[0].status == STATUS_FAILED


def test_memory_shadow_write_failed() -> None:
    src = _source()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=lambda _s: _compose_failed(COMPOSE_MEMORY_FAILED),
            is_indexing_busy=lambda: False,
        )
    assert result.plan_results[0].reason == REASON_MEMORY_SHADOW_WRITE_FAILED
    assert result.plan_results[0].status == STATUS_FAILED


def test_interrupted() -> None:
    src = _source()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=MagicMock(side_effect=KeyboardInterrupt()),
            is_indexing_busy=lambda: False,
        )
    assert result.plan_results[0].reason == REASON_INTERRUPTED
    assert result.plan_results[0].status == STATUS_FAILED


def test_one_plan_failure_does_not_stop_later_plans() -> None:
    src = _source()
    calls: list[str] = []

    def index(_s: MagicMock) -> IndexIntegrateResult:
        calls.append("x")
        if len(calls) == 1:
            return _compose_failed(COMPOSE_FETCH_FAILED)
        return _compose_ok()

    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan("a"), _plan("b")),
            _settings(),
            index_source=index,
            is_indexing_busy=lambda: False,
        )
    assert result.failed == 1
    assert result.succeeded == 1
    assert [r.plan_id for r in result.plan_results] == ["a", "b"]


def test_no_direct_memory_claim_evidence_writes() -> None:
    db = MagicMock()
    src = _source()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        execute_selected_investigations(
            db,
            (_plan(),),
            _settings(),
            index_source=lambda _s: _compose_ok(),
            is_indexing_busy=lambda: False,
        )
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_independent_of_knowledge_os_executive_enabled(monkeypatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_OS_EXECUTIVE_ENABLED", "true")
    src = _source()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=lambda _s: _compose_ok(),
            is_indexing_busy=lambda: False,
        )
    assert result.succeeded == 1


def test_default_step_059_off_causes_no_investigation_io() -> None:
    invoker = MaintenanceCycleInvoker(interval_seconds=5)
    with (
        patch(
            "app.services.executive.maintenance_cycle_invoker.SessionLocal"
        ) as session_factory,
        patch(
            "app.services.executive.maintenance_cycle_invoker.orchestrate_maintenance_cycle"
        ) as orch,
        patch(
            "app.services.executive.maintenance_cycle_invoker.execute_selected_investigations"
        ) as exec_fn,
    ):
        session = MagicMock()
        session_factory.return_value = session
        orch.return_value = MaintenanceCycleResult(
            status="ok",
            skip_reason="flag_off",
            selected_plans=(),
            plans_considered=0,
        )
        invoker.run_once()
        exec_fn.assert_not_called()


def test_invoker_executes_when_plans_selected() -> None:
    invoker = MaintenanceCycleInvoker(interval_seconds=5)
    plan = _plan()
    with (
        patch(
            "app.services.executive.maintenance_cycle_invoker.SessionLocal"
        ) as session_factory,
        patch(
            "app.services.executive.maintenance_cycle_invoker.orchestrate_maintenance_cycle"
        ) as orch,
        patch(
            "app.services.executive.maintenance_cycle_invoker.SettingsRepository"
        ) as settings_repo,
        patch(
            "app.services.executive.maintenance_cycle_invoker.execute_selected_investigations"
        ) as exec_fn,
    ):
        session = MagicMock()
        session_factory.return_value = session
        settings = _settings()
        settings_repo.return_value.get_or_create.return_value = settings
        orch.return_value = MaintenanceCycleResult(
            status="ok",
            skip_reason=None,
            selected_plans=(plan,),
            plans_considered=1,
        )
        invoker.run_once()
        exec_fn.assert_called_once_with(session, (plan,), settings)


def test_claim_traversal_resolves_single_source() -> None:
    memory = MagicMock()
    memory.get_observation_ref.side_effect = lambda **kw: (
        None
        if kw.get("observation_ref_id") == 999
        else _obs(kw["observation_ref_id"], 7)
    )
    memory.list_evidence_links_for_claim.return_value = ([_link(1, 20)], 1)
    src = _source(7)
    with patch(
        "app.services.executive.investigation_target.SourceRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = src
        res = resolve_investigation_target(
            MagicMock(),
            _plan(observation_ref_ids=(), claim_ids=(1,)),
            _settings(),
            memory=memory,
        )
    assert res.source is src
    assert res.reason is None


def test_default_uses_index_and_integrate_entrypoint() -> None:
    src = _source()
    with (
        patch(
            "app.services.executive.investigation_execution.resolve_investigation_target",
            return_value=SimpleNamespace(source=src, reason=None),
        ),
        patch(
            "app.services.index_integrate.index_and_integrate",
            return_value=_compose_ok(),
        ) as compose,
        patch(
            "app.services.source_repository_service.SourceRepositoryService"
        ) as svc_cls,
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            is_indexing_busy=lambda: False,
        )
    assert result.succeeded == 1
    compose.assert_called_once()
    svc_cls.assert_not_called()


def test_downstream_result_is_opaque_string() -> None:
    src = _source()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=lambda _s: _compose_ok(),
            is_indexing_busy=lambda: False,
        )
    opaque = result.plan_results[0].downstream_result
    assert opaque is not None
    assert isinstance(opaque, str)
    assert "succeeded" in opaque
    assert "indexed: 3 chunks" in opaque


def test_indexed_without_compose_success_is_not_sufficient() -> None:
    """Bare index-only 'indexed' shape must not be treated as Step 060 success."""
    src = _source()
    with patch(
        "app.services.executive.investigation_execution.resolve_investigation_target",
        return_value=SimpleNamespace(source=src, reason=None),
    ):
        result = execute_selected_investigations(
            MagicMock(),
            (_plan(),),
            _settings(),
            index_source=lambda _s: SimpleNamespace(status="indexed", detail="ok"),
            is_indexing_busy=lambda: False,
        )
    assert result.plan_results[0].status == STATUS_FAILED
    assert result.plan_results[0].reason == REASON_INDEX_FAILED
