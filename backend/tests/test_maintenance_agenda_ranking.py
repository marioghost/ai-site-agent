"""RFC-100 Step 058 — EpistemicMaintenanceService agenda ranking (unit)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.epistemic_maintenance import (
    ACTION_SEEK_ADJUDICATION,
    ACTION_SEEK_CORROBORATION,
    EpistemicMaintenanceService,
)
from app.services.tension_surfacing import (
    TENSION_CONFLICT,
    TENSION_SUPPORT_DEFICIT,
    TensionView,
)

pytestmark = pytest.mark.unit


def _tv(
    tension_type: str,
    claim_ids: tuple[int, ...] = (),
    *,
    observation_ref_ids: tuple[int, ...] = (),
    evidence_link_ids: tuple[int, ...] = (),
    summary: str = "fixture",
) -> TensionView:
    return TensionView(
        tension_type=tension_type,
        claim_ids=claim_ids,
        observation_ref_ids=observation_ref_ids,
        evidence_link_ids=evidence_link_ids,
        summary=summary,
    )


def _service() -> EpistemicMaintenanceService:
    return EpistemicMaintenanceService(MagicMock())


def test_rank_empty_input_returns_empty() -> None:
    assert _service().rank([]) == []


def test_rank_single_support_deficit() -> None:
    plans = _service().rank([_tv(TENSION_SUPPORT_DEFICIT, (10,))])
    assert len(plans) == 1
    assert plans[0].tension_type == TENSION_SUPPORT_DEFICIT
    assert plans[0].action == ACTION_SEEK_CORROBORATION
    assert plans[0].claim_ids == (10,)


def test_rank_single_conflict() -> None:
    plans = _service().rank([_tv(TENSION_CONFLICT, (20,))])
    assert len(plans) == 1
    assert plans[0].tension_type == TENSION_CONFLICT
    assert plans[0].action == ACTION_SEEK_ADJUDICATION


def test_rank_conflict_outranks_support_deficit() -> None:
    plans = _service().rank(
        [
            _tv(TENSION_SUPPORT_DEFICIT, (1,)),
            _tv(TENSION_CONFLICT, (99,)),
        ]
    )
    assert [p.tension_type for p in plans] == [
        TENSION_CONFLICT,
        TENSION_SUPPORT_DEFICIT,
    ]
    assert plans[0].priority > plans[1].priority


def test_rank_tie_break_claim_ids_ascending() -> None:
    plans = _service().rank(
        [
            _tv(TENSION_SUPPORT_DEFICIT, (30,)),
            _tv(TENSION_SUPPORT_DEFICIT, (10,)),
            _tv(TENSION_SUPPORT_DEFICIT, (20,)),
        ]
    )
    assert [p.claim_ids[0] for p in plans] == [10, 20, 30]


def test_rank_empty_claim_ids_sort_last_within_type() -> None:
    plans = _service().rank(
        [
            _tv(TENSION_SUPPORT_DEFICIT, ()),
            _tv(TENSION_SUPPORT_DEFICIT, (5,)),
        ]
    )
    assert plans[0].claim_ids == (5,)
    assert plans[1].claim_ids == ()


def test_rank_deterministic_same_inputs() -> None:
    tensions = [
        _tv(TENSION_CONFLICT, (3,), summary="a"),
        _tv(TENSION_SUPPORT_DEFICIT, (1,), summary="b"),
        _tv(TENSION_CONFLICT, (2,), summary="c"),
    ]
    svc = _service()
    assert svc.rank(tensions) == svc.rank(list(tensions))


def test_rank_none_calls_surface_tensions_only() -> None:
    surfacing = MagicMock()
    surfacing.surface_tensions.return_value = [
        _tv(TENSION_CONFLICT, (7,)),
    ]
    plans = EpistemicMaintenanceService(surfacing).rank()
    surfacing.surface_tensions.assert_called_once_with()
    assert len(plans) == 1
    assert plans[0].claim_ids == (7,)


def test_rank_does_not_touch_session_when_tensions_provided() -> None:
    surfacing = MagicMock()
    _service_with = EpistemicMaintenanceService(surfacing)
    _service_with.rank([_tv(TENSION_SUPPORT_DEFICIT, (1,))])
    surfacing.surface_tensions.assert_not_called()
