"""Typed provenance scope for Epistemic Memory / Epistemic Health (demo-ready).

Rules:
- ``test``: claim.provenance_kind == \"test\" OR claim.attributed_to == \"fixture\"
- ``real``: not test (includes source_intelligence and other non-test kinds)
- ``all``: no filter

Observation / evidence rows are test-owned when provenance_kind == \"test\"
or when linked exclusively to test-scoped claims.
"""
from __future__ import annotations

from enum import Enum
from typing import Iterable

from sqlalchemy import or_
from sqlalchemy.sql import ColumnElement

from app.models.epistemic_memory import EpistemicClaim


class ProvenanceScope(str, Enum):
    REAL = "real"
    TEST = "test"
    ALL = "all"


PROVENANCE_KIND_TEST = "test"
ATTRIBUTED_TO_FIXTURE = "fixture"
PROVENANCE_KIND_SOURCE_INTELLIGENCE = "source_intelligence"


def parse_provenance_scope(raw: str | None, *, default: ProvenanceScope = ProvenanceScope.REAL) -> ProvenanceScope:
    if raw is None or raw == "":
        return default
    try:
        return ProvenanceScope(raw.lower())
    except ValueError as exc:
        raise ValueError(
            f"Invalid provenance_scope={raw!r}; expected real|test|all"
        ) from exc


def is_test_claim(
    *,
    provenance_kind: str | None,
    attributed_to: str | None,
) -> bool:
    return (
        (provenance_kind or "") == PROVENANCE_KIND_TEST
        or (attributed_to or "") == ATTRIBUTED_TO_FIXTURE
    )


def is_test_observation(*, provenance_kind: str | None) -> bool:
    return (provenance_kind or "") == PROVENANCE_KIND_TEST


def is_test_evidence(*, provenance_kind: str | None) -> bool:
    return (provenance_kind or "") == PROVENANCE_KIND_TEST


def claim_matches_scope(
    *,
    provenance_kind: str | None,
    attributed_to: str | None,
    scope: ProvenanceScope,
) -> bool:
    if scope is ProvenanceScope.ALL:
        return True
    test = is_test_claim(provenance_kind=provenance_kind, attributed_to=attributed_to)
    if scope is ProvenanceScope.TEST:
        return test
    return not test


def claim_sql_filter(scope: ProvenanceScope) -> ColumnElement[bool] | None:
    """SQLAlchemy filter for EpistemicClaim rows, or None for ALL."""
    if scope is ProvenanceScope.ALL:
        return None
    test_expr = or_(
        EpistemicClaim.provenance_kind == PROVENANCE_KIND_TEST,
        EpistemicClaim.attributed_to == ATTRIBUTED_TO_FIXTURE,
    )
    if scope is ProvenanceScope.TEST:
        return test_expr
    return ~test_expr


def classify_tension_scope(
    claim_is_test: Iterable[bool],
) -> str:
    """Return real|test|mixed for a tension's involved claims."""
    flags = list(claim_is_test)
    if not flags:
        return ProvenanceScope.REAL.value
    if all(flags):
        return ProvenanceScope.TEST.value
    if not any(flags):
        return ProvenanceScope.REAL.value
    return "mixed"


def tension_matches_scope(tension_scope: str, filter_scope: ProvenanceScope) -> bool:
    if filter_scope is ProvenanceScope.ALL:
        return True
    if filter_scope is ProvenanceScope.REAL:
        return tension_scope == ProvenanceScope.REAL.value
    if filter_scope is ProvenanceScope.TEST:
        return tension_scope == ProvenanceScope.TEST.value
    return False
