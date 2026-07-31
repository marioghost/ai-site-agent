"""RFC-100 Step 059 — maintenance cycle orchestration (unit)."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.epistemic_maintenance import (
    ACTION_SEEK_ADJUDICATION,
    ACTION_SEEK_CORROBORATION,
    InvestigationPlan,
)
from app.services.executive.maintenance_cycle_invoker import MaintenanceCycleInvoker
from app.services.executive.maintenance_orchestration import (
    operational_budget,
    orchestrate_maintenance_cycle,
    rollout_flag_enabled,
)
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

pytestmark = pytest.mark.unit

_FLAG = "MAINTENANCE_EXECUTION_ENABLED"
_BUDGET = "MAINTENANCE_INVESTIGATIONS_PER_CYCLE"


def _plan(plan_id: str, *, priority: float = 1.0) -> InvestigationPlan:
    return InvestigationPlan(
        plan_id=plan_id,
        tension_type="support_deficit",
        claim_ids=(1,),
        observation_ref_ids=(),
        evidence_link_ids=(),
        action=ACTION_SEEK_CORROBORATION,
        priority=priority,
        rationale="fixture",
    )


def _env(**kwargs: str) -> dict[str, str]:
    return dict(kwargs)


def test_flag_disabled_returns_flag_off() -> None:
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "false", _BUDGET: "5"}),
    )
    assert result.status == STATUS_OK
    assert result.skip_reason == SKIP_FLAG_OFF
    assert result.selected_plans == ()
    assert result.plans_considered == 0


def test_budget_zero_returns_budget_zero() -> None:
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "0"}),
    )
    assert result.status == STATUS_OK
    assert result.skip_reason == SKIP_BUDGET_ZERO
    assert result.selected_plans == ()


def test_empty_plans_returns_empty_plans() -> None:
    rank = MagicMock()
    rank.rank.return_value = []
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "3"}),
        rank_service=rank,
    )
    assert result.status == STATUS_OK
    assert result.skip_reason == SKIP_EMPTY_PLANS
    assert result.selected_plans == ()
    assert result.plans_considered == 0
    rank.rank.assert_called_once_with()


def test_selects_first_n_in_existing_rank_order() -> None:
    plans = [_plan("a", priority=2.0), _plan("b"), _plan("c"), _plan("d")]
    rank = MagicMock()
    rank.rank.return_value = plans
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "2"}),
        rank_service=rank,
    )
    assert result.status == STATUS_OK
    assert result.skip_reason is None
    assert [p.plan_id for p in result.selected_plans] == ["a", "b"]
    assert result.plans_considered == 4


def test_budget_larger_than_plan_count() -> None:
    plans = [_plan("a"), _plan("b")]
    rank = MagicMock()
    rank.rank.return_value = plans
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "10"}),
        rank_service=rank,
    )
    assert result.skip_reason is None
    assert [p.plan_id for p in result.selected_plans] == ["a", "b"]
    assert result.plans_considered == 2


def test_already_running_returns_skip() -> None:
    plans = [_plan("a")]
    rank = MagicMock()
    started = threading.Event()
    release = threading.Event()

    def slow_rank() -> list[InvestigationPlan]:
        started.set()
        release.wait(timeout=5)
        return plans

    rank.rank.side_effect = slow_rank
    results: list = []

    def first() -> None:
        results.append(
            orchestrate_maintenance_cycle(
                MagicMock(),
                environ=_env(**{_FLAG: "true", _BUDGET: "1"}),
                rank_service=rank,
            )
        )

    t = threading.Thread(target=first)
    t.start()
    assert started.wait(timeout=5)

    second = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "1"}),
        rank_service=MagicMock(),
    )
    assert second.status == STATUS_OK
    assert second.skip_reason == SKIP_ALREADY_RUNNING
    assert second.selected_plans == ()

    release.set()
    t.join(timeout=5)
    assert results[0].status == STATUS_OK
    assert results[0].skip_reason is None


def test_rank_failure_returns_error() -> None:
    rank = MagicMock()
    rank.rank.side_effect = RuntimeError("rank boom")
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "2"}),
        rank_service=rank,
    )
    assert result.status == STATUS_ERROR
    assert result.skip_reason == SKIP_RANK_FAILED
    assert result.selected_plans == ()
    assert result.plans_considered == 0


def test_single_flight_lock_released_after_failure() -> None:
    rank = MagicMock()
    rank.rank.side_effect = RuntimeError("boom")
    env = _env(**{_FLAG: "true", _BUDGET: "1"})
    first = orchestrate_maintenance_cycle(MagicMock(), environ=env, rank_service=rank)
    assert first.skip_reason == SKIP_RANK_FAILED

    rank2 = MagicMock()
    rank2.rank.return_value = [_plan("recovered")]
    second = orchestrate_maintenance_cycle(
        MagicMock(), environ=env, rank_service=rank2
    )
    assert second.status == STATUS_OK
    assert second.skip_reason is None
    assert second.selected_plans[0].plan_id == "recovered"


def test_independent_of_knowledge_os_executive_enabled(monkeypatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_OS_EXECUTIVE_ENABLED", "true")
    rank = MagicMock()
    rank.rank.return_value = [_plan("x")]
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "1"}),
        rank_service=rank,
    )
    assert result.skip_reason is None
    assert len(result.selected_plans) == 1

    monkeypatch.setenv("KNOWLEDGE_OS_EXECUTIVE_ENABLED", "false")
    result_off = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "1"}),
        rank_service=rank,
    )
    assert result_off.skip_reason is None


def test_invalid_boolean_fails_closed() -> None:
    assert rollout_flag_enabled(_env(**{_FLAG: "maybe"})) is False
    assert rollout_flag_enabled(_env(**{_FLAG: "TRUEISH"})) is False
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "banana", _BUDGET: "5"}),
    )
    assert result.skip_reason == SKIP_FLAG_OFF


def test_missing_budget_fails_closed() -> None:
    assert operational_budget(_env(**{_FLAG: "true"})) == 0
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true"}),
    )
    assert result.skip_reason == SKIP_BUDGET_ZERO


def test_invalid_budget_fails_closed() -> None:
    assert operational_budget(_env(**{_BUDGET: "abc"})) == 0
    assert operational_budget(_env(**{_BUDGET: "1.5"})) == 0
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "nope"}),
    )
    assert result.skip_reason == SKIP_BUDGET_ZERO


def test_negative_budget_fails_closed() -> None:
    assert operational_budget(_env(**{_BUDGET: "-3"})) == 0
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "-1"}),
    )
    assert result.skip_reason == SKIP_BUDGET_ZERO


def test_no_gateway_call() -> None:
    """Cycle selects plans only; never dispatches Gateway / InvestigationCommand."""
    rank = MagicMock()
    rank.rank.return_value = [_plan("a")]
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "1"}),
        rank_service=rank,
    )
    assert result.skip_reason is None
    assert rank.rank.call_count == 1
    import ast
    import app.services.executive.maintenance_orchestration as orch_mod

    tree = ast.parse(open(orch_mod.__file__, encoding="utf-8").read())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
            imported.update(alias.name for alias in node.names)
    forbidden = {
        "InvestigationCommand",
        "investigation_gateway",
        "InvestigationGateway",
    }
    assert forbidden.isdisjoint(imported)
    assert rank.rank.call_count == 1


def test_no_memory_write() -> None:
    db = MagicMock()
    rank = MagicMock()
    rank.rank.return_value = [_plan("a")]
    orchestrate_maintenance_cycle(
        db,
        environ=_env(**{_FLAG: "true", _BUDGET: "1"}),
        rank_service=rank,
    )
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.flush.assert_not_called()
    db.execute.assert_not_called()


def test_periodic_invocation_calls_cycle_entry() -> None:
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
        orch.assert_called_once_with(session)
        exec_fn.assert_not_called()
        session.close.assert_called_once()


def test_default_configuration_causes_no_work() -> None:
    rank = MagicMock()
    # Empty environ → flag off (missing) and budget 0
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ={},
        rank_service=rank,
    )
    assert result.skip_reason == SKIP_FLAG_OFF
    rank.rank.assert_not_called()


def test_rollout_true_variants() -> None:
    for value in ("1", "true", "TRUE", "yes", "on"):
        assert rollout_flag_enabled(_env(**{_FLAG: value})) is True


def test_selected_plans_are_investigation_plan_dtos() -> None:
    rank = MagicMock()
    rank.rank.return_value = [
        InvestigationPlan(
            plan_id="c1",
            tension_type="conflict",
            claim_ids=(9,),
            observation_ref_ids=(),
            evidence_link_ids=(),
            action=ACTION_SEEK_ADJUDICATION,
            priority=2.0,
            rationale="r",
        )
    ]
    result = orchestrate_maintenance_cycle(
        MagicMock(),
        environ=_env(**{_FLAG: "true", _BUDGET: "1"}),
        rank_service=rank,
    )
    assert isinstance(result.selected_plans[0], InvestigationPlan)


def test_invoker_loop_calls_run_once_then_waits() -> None:
    invoker = MaintenanceCycleInvoker(interval_seconds=5)
    calls = {"n": 0}

    def fake_run() -> None:
        calls["n"] += 1
        invoker.stop()

    with patch.object(invoker, "run_once", side_effect=fake_run):
        invoker.start()
        deadline = time.time() + 2
        while calls["n"] == 0 and time.time() < deadline:
            time.sleep(0.05)
        assert calls["n"] >= 1
        if invoker._thread is not None:
            invoker._thread.join(timeout=2)
