"""RFC-100 Step 061 — maintenance / investigation metrics (unit)."""
from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.settings import Settings
from app.services.epistemic_maintenance import (
    ACTION_SEEK_CORROBORATION,
    InvestigationPlan,
)
from app.services.executive.investigation_types import (
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCEEDED,
    InvestigationCycleResult,
    InvestigationPlanResult,
)
from app.services.executive.maintenance_cycle_invoker import MaintenanceCycleInvoker
from app.services.executive.maintenance_types import (
    SKIP_ALREADY_RUNNING,
    SKIP_BUDGET_ZERO,
    SKIP_EMPTY_PLANS,
    SKIP_FLAG_OFF,
    SKIP_RANK_FAILED,
    STATUS_ERROR,
    STATUS_OK,
    MaintenanceCycleResult,
)
from app.services.maintenance_metrics import (
    observe_maintenance_metrics,
    reset_maintenance_counters,
)
from app.services.maintenance_metrics.counters import (
    MaintenanceInvestigationCounters,
    get_maintenance_counters,
)
from app.services.operational_metrics_service import OperationalMetricsService
from app.services.tension_surfacing import METRICS_CLAIM_SCAN_LIMIT, TensionCountSummary

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_counters() -> None:
    reset_maintenance_counters()
    yield
    reset_maintenance_counters()


def _plan(plan_id: str = "p1") -> InvestigationPlan:
    return InvestigationPlan(
        plan_id=plan_id,
        tension_type="support_deficit",
        claim_ids=(1,),
        observation_ref_ids=(10,),
        evidence_link_ids=(),
        action=ACTION_SEEK_CORROBORATION,
        priority=1.0,
        rationale="fixture",
    )


def _cycle(
    *,
    status: str = STATUS_OK,
    skip_reason: str | None = None,
    selected: tuple[InvestigationPlan, ...] = (),
    plans_considered: int = 0,
) -> MaintenanceCycleResult:
    return MaintenanceCycleResult(
        status=status,
        skip_reason=skip_reason,
        selected_plans=selected,
        plans_considered=plans_considered,
    )


def _plan_result(status: str, plan_id: str = "p1") -> InvestigationPlanResult:
    return InvestigationPlanResult(
        status=status,
        reason="index_failed" if status == STATUS_FAILED else None,
        plan_id=plan_id,
        source_id=1,
        url="https://example.com/x",
        downstream_result=None,
    )


def _investigation(*statuses: str) -> InvestigationCycleResult:
    results = tuple(
        _plan_result(status, plan_id=f"p{i}") for i, status in enumerate(statuses)
    )
    return InvestigationCycleResult(
        plan_results=results,
        succeeded=sum(1 for s in statuses if s == STATUS_SUCCEEDED),
        skipped=sum(1 for s in statuses if s == STATUS_SKIPPED),
        failed=sum(1 for s in statuses if s == STATUS_FAILED),
    )


def _snap():
    return get_maintenance_counters().snapshot()


def test_one_cycle_increments_cycle_counter_by_one() -> None:
    observe_maintenance_metrics(_cycle(skip_reason=SKIP_FLAG_OFF))
    assert _snap().maintenance_cycles_total == 1


@pytest.mark.parametrize(
    "skip_reason",
    [
        SKIP_FLAG_OFF,
        SKIP_BUDGET_ZERO,
        SKIP_EMPTY_PLANS,
        SKIP_ALREADY_RUNNING,
        SKIP_RANK_FAILED,
    ],
)
def test_skip_reason_increments_cycle_counter(skip_reason: str) -> None:
    status = STATUS_ERROR if skip_reason == SKIP_RANK_FAILED else STATUS_OK
    observe_maintenance_metrics(_cycle(status=status, skip_reason=skip_reason))
    assert _snap().maintenance_cycles_total == 1
    assert _snap().investigations_planned == 0
    assert _snap().investigations_failed_total == 0


def test_selected_work_increments_cycle_once() -> None:
    plans = (_plan("a"), _plan("b"))
    observe_maintenance_metrics(
        _cycle(selected=plans, plans_considered=99),
        _investigation(STATUS_SUCCEEDED, STATUS_SUCCEEDED),
    )
    assert _snap().maintenance_cycles_total == 1


def test_planned_equals_len_selected_plans() -> None:
    plans = (_plan("a"), _plan("b"), _plan("c"))
    observe_maintenance_metrics(
        _cycle(selected=plans, plans_considered=50),
        _investigation(STATUS_SUCCEEDED, STATUS_SUCCEEDED, STATUS_SUCCEEDED),
    )
    assert _snap().investigations_planned == 3


def test_planned_never_uses_plans_considered() -> None:
    observe_maintenance_metrics(
        _cycle(selected=(_plan(),), plans_considered=42),
        _investigation(STATUS_SUCCEEDED),
    )
    assert _snap().investigations_planned == 1
    assert _snap().investigations_planned != 42


def test_zero_selected_adds_zero_planned() -> None:
    observe_maintenance_metrics(
        _cycle(skip_reason=SKIP_EMPTY_PLANS, plans_considered=7)
    )
    assert _snap().investigations_planned == 0


def test_one_failed_plan_increments_failed_by_one() -> None:
    observe_maintenance_metrics(
        _cycle(selected=(_plan(),)),
        _investigation(STATUS_FAILED),
    )
    assert _snap().investigations_failed_total == 1


def test_multiple_failed_plans_increment_by_exact_count() -> None:
    observe_maintenance_metrics(
        _cycle(selected=(_plan("a"), _plan("b"), _plan("c"))),
        _investigation(STATUS_FAILED, STATUS_FAILED, STATUS_SUCCEEDED),
    )
    assert _snap().investigations_failed_total == 2


def test_skipped_plans_do_not_increment_failed() -> None:
    observe_maintenance_metrics(
        _cycle(selected=(_plan(),)),
        _investigation(STATUS_SKIPPED),
    )
    assert _snap().investigations_failed_total == 0


def test_succeeded_plans_do_not_increment_failed() -> None:
    observe_maintenance_metrics(
        _cycle(selected=(_plan(),)),
        _investigation(STATUS_SUCCEEDED),
    )
    assert _snap().investigations_failed_total == 0


def test_missing_investigation_cycle_result_adds_zero_failed() -> None:
    observe_maintenance_metrics(_cycle(skip_reason=SKIP_FLAG_OFF))
    assert _snap().investigations_failed_total == 0


def test_single_invocation_observes_dtos_once_on_path() -> None:
    plans = (_plan("a"), _plan("b"))
    inv = _investigation(STATUS_FAILED, STATUS_SUCCEEDED)
    observe_maintenance_metrics(_cycle(selected=plans, plans_considered=9), inv)
    snap = _snap()
    assert snap.maintenance_cycles_total == 1
    assert snap.investigations_planned == 2
    assert snap.investigations_failed_total == 1


def test_thread_safe_concurrent_increments() -> None:
    cycle = _cycle(selected=(_plan(),), plans_considered=1)
    inv = _investigation(STATUS_FAILED)

    def _once() -> None:
        observe_maintenance_metrics(cycle, inv)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: _once(), range(40)))
    snap = _snap()
    assert snap.maintenance_cycles_total == 40
    assert snap.investigations_planned == 40
    assert snap.investigations_failed_total == 40


def test_metrics_failure_does_not_change_059_result() -> None:
    cycle = _cycle(skip_reason=SKIP_FLAG_OFF)
    original = (
        cycle.status,
        cycle.skip_reason,
        cycle.selected_plans,
        cycle.plans_considered,
    )
    with patch(
        "app.services.maintenance_metrics.observe.get_maintenance_counters",
        side_effect=RuntimeError("boom"),
    ):
        observe_maintenance_metrics(cycle)
    assert (
        cycle.status,
        cycle.skip_reason,
        cycle.selected_plans,
        cycle.plans_considered,
    ) == original


def test_metrics_failure_does_not_change_060_result() -> None:
    cycle = _cycle(selected=(_plan(),))
    inv = _investigation(STATUS_FAILED)
    before = (inv.succeeded, inv.skipped, inv.failed, inv.plan_results)
    with patch(
        "app.services.maintenance_metrics.observe.get_maintenance_counters",
        side_effect=RuntimeError("boom"),
    ):
        observe_maintenance_metrics(cycle, inv)
    assert (inv.succeeded, inv.skipped, inv.failed, inv.plan_results) == before


def test_invoker_observes_step_060_result_once() -> None:
    invoker = MaintenanceCycleInvoker(interval_seconds=5)
    plan = _plan()
    inv_result = _investigation(STATUS_FAILED)
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
            "app.services.executive.maintenance_cycle_invoker.execute_selected_investigations",
            return_value=inv_result,
        ) as exec_fn,
        patch(
            "app.services.executive.maintenance_cycle_invoker.observe_maintenance_metrics"
        ) as observe,
    ):
        session = MagicMock()
        session_factory.return_value = session
        settings_repo.return_value.get_or_create.return_value = MagicMock()
        orch.return_value = MaintenanceCycleResult(
            status=STATUS_OK,
            skip_reason=None,
            selected_plans=(plan,),
            plans_considered=1,
        )
        invoker.run_once()
        exec_fn.assert_called_once()
        observe.assert_called_once_with(orch.return_value, inv_result)


def test_invoker_observes_cycle_without_060_when_no_selection() -> None:
    invoker = MaintenanceCycleInvoker(interval_seconds=5)
    cycle = _cycle(skip_reason=SKIP_FLAG_OFF)
    with (
        patch(
            "app.services.executive.maintenance_cycle_invoker.SessionLocal"
        ) as session_factory,
        patch(
            "app.services.executive.maintenance_cycle_invoker.orchestrate_maintenance_cycle",
            return_value=cycle,
        ),
        patch(
            "app.services.executive.maintenance_cycle_invoker.execute_selected_investigations"
        ) as exec_fn,
        patch(
            "app.services.executive.maintenance_cycle_invoker.observe_maintenance_metrics"
        ) as observe,
    ):
        session_factory.return_value = MagicMock()
        invoker.run_once()
        exec_fn.assert_not_called()
        observe.assert_called_once_with(cycle, None)


def _patch_empty_gauges(monkeypatch) -> None:
    state = Settings(knowledge_version=1, memory_version=1)

    class FakeRepo:
        def get_or_create(self) -> Settings:
            return state

        def save(self, settings: Settings) -> Settings:
            return settings

    monkeypatch.setattr(
        "app.services.memory_version_service.SettingsRepository",
        lambda db: FakeRepo(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: FakeRepo(),
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.EpistemicMemoryService",
        lambda db: MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.operational_metrics_service.TensionSurfacingService",
        lambda memory: MagicMock(
            summarize_counts=lambda **kw: TensionCountSummary(
                open_tensions=0,
                support_deficit_tensions=0,
                conflict_tensions=0,
                claim_scan_limit=METRICS_CLAIM_SCAN_LIMIT,
            )
        ),
    )


def test_api_metrics_exposes_all_three_counters(monkeypatch) -> None:
    _patch_empty_gauges(monkeypatch)
    observe_maintenance_metrics(
        _cycle(selected=(_plan("a"), _plan("b"))),
        _investigation(STATUS_FAILED, STATUS_SUCCEEDED),
    )

    def override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        res = client.get("/api/metrics")
        assert res.status_code == 200
        text = res.text
        assert "# TYPE kos_maintenance_cycles_total counter" in text
        assert re.search(r"^kos_maintenance_cycles_total 1$", text, re.MULTILINE)
        assert "# TYPE kos_investigations_planned counter" in text
        assert re.search(r"^kos_investigations_planned 2$", text, re.MULTILINE)
        assert "# TYPE kos_investigations_failed_total counter" in text
        assert re.search(r"^kos_investigations_failed_total 1$", text, re.MULTILINE)
        assert "kos_tension_resolved_total" not in text
    finally:
        app.dependency_overrides.clear()


def test_counters_reset_with_new_service_instance() -> None:
    observe_maintenance_metrics(_cycle(selected=(_plan(),)), _investigation(STATUS_FAILED))
    assert _snap().maintenance_cycles_total == 1
    fresh = MaintenanceInvestigationCounters()
    assert fresh.snapshot().maintenance_cycles_total == 0
    assert fresh.snapshot().investigations_planned == 0
    assert fresh.snapshot().investigations_failed_total == 0
    reset_maintenance_counters()
    assert _snap().maintenance_cycles_total == 0


def test_no_tension_resolved_metric_in_prometheus(monkeypatch) -> None:
    _patch_empty_gauges(monkeypatch)
    text = OperationalMetricsService(db=None).render_prometheus()
    assert "kos_tension_resolved_total" not in text


def test_observe_does_not_call_rank_or_execution() -> None:
    with (
        patch("app.services.epistemic_maintenance.EpistemicMaintenanceService") as maint,
        patch(
            "app.services.executive.investigation_execution.execute_selected_investigations"
        ) as exec_fn,
        patch("app.services.index_integrate.index_and_integrate") as compose,
    ):
        observe_maintenance_metrics(
            _cycle(selected=(_plan(),), plans_considered=3),
            _investigation(STATUS_SUCCEEDED),
        )
        maint.assert_not_called()
        exec_fn.assert_not_called()
        compose.assert_not_called()


def test_observe_source_does_not_reference_forbidden_callees() -> None:
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "app/services/maintenance_metrics"
    text = "\n".join(p.read_text(encoding="utf-8") for p in src.glob("*.py"))
    assert "rank(" not in text
    assert "execute_selected_investigations" not in text
    assert "index_and_integrate" not in text
    assert "shadow_write" not in text
    assert "build_profile" not in text
