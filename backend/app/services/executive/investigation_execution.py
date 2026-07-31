"""Investigation execution (RFC-100 Step 060).

Consumes Step 059 selected plans; maps seek_* → fetch; resolves one source;
dispatches via the project's authoritative single-source Index → Integrate
entrypoint (`index_and_integrate`).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.models.source import Source
from app.services.epistemic_maintenance import (
    ACTION_SEEK_ADJUDICATION,
    ACTION_SEEK_CORROBORATION,
    InvestigationPlan,
)
from app.services.executive.investigation_target import resolve_investigation_target
from app.services.executive.investigation_types import (
    REASON_CONTENT_UNCHANGED,
    REASON_FETCH_FAILED,
    REASON_INDEX_FAILED,
    REASON_INDEXING_BUSY,
    REASON_INTERRUPTED,
    REASON_MEMORY_SHADOW_WRITE_FAILED,
    REASON_PARSE_FAILED,
    REASON_SI_FAILED,
    REASON_UNSUPPORTED_ACTION,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCEEDED,
    VERB_FETCH,
    InvestigationCycleResult,
    InvestigationDispatch,
    InvestigationPlanResult,
)
from app.services.index_integrate.types import (
    REASON_CONTENT_UNCHANGED as COMPOSE_CONTENT_UNCHANGED,
    REASON_FETCH_FAILED as COMPOSE_FETCH_FAILED,
    REASON_INDEX_FAILED as COMPOSE_INDEX_FAILED,
    REASON_MEMORY_SHADOW_WRITE_FAILED as COMPOSE_MEMORY_FAILED,
    REASON_PARSE_FAILED as COMPOSE_PARSE_FAILED,
    REASON_SI_FAILED as COMPOSE_SI_FAILED,
    STATUS_FAILED as COMPOSE_FAILED,
    STATUS_SKIPPED as COMPOSE_SKIPPED,
    STATUS_SUCCEEDED as COMPOSE_SUCCEEDED,
)

_SUPPORTED = frozenset({ACTION_SEEK_CORROBORATION, ACTION_SEEK_ADJUDICATION})

_COMPOSE_REASON_MAP = {
    COMPOSE_CONTENT_UNCHANGED: REASON_CONTENT_UNCHANGED,
    COMPOSE_FETCH_FAILED: REASON_FETCH_FAILED,
    COMPOSE_PARSE_FAILED: REASON_PARSE_FAILED,
    COMPOSE_INDEX_FAILED: REASON_INDEX_FAILED,
    COMPOSE_SI_FAILED: REASON_SI_FAILED,
    COMPOSE_MEMORY_FAILED: REASON_MEMORY_SHADOW_WRITE_FAILED,
}

# Injectable for tests — default uses Index → Integrate compose.
AuthoritativeIndexIntegrateFn = Callable[[Source], Any]
BusyCheckFn = Callable[[], bool]


def execute_selected_investigations(
    db: Session,
    selected_plans: tuple[InvestigationPlan, ...] | list[InvestigationPlan],
    settings: Settings,
    *,
    index_source: AuthoritativeIndexIntegrateFn | None = None,
    is_indexing_busy: BusyCheckFn | None = None,
) -> InvestigationCycleResult:
    """Public Step 060 entry: execute fetch investigations for selected plans.

    Preserves input order. Does not re-rank or re-select. Does not call Step 058 rank.
    Not gated by KNOWLEDGE_OS_EXECUTIVE_ENABLED (Step 059 gates remain sole enablement).
    """
    index_fn = index_source or _default_index_integrate(db, settings)
    busy_fn = is_indexing_busy or _default_busy_check

    results: list[InvestigationPlanResult] = []
    for plan in selected_plans:
        results.append(
            _execute_one(db, plan, settings, index_fn=index_fn, busy_fn=busy_fn)
        )

    succeeded = sum(1 for r in results if r.status == STATUS_SUCCEEDED)
    skipped = sum(1 for r in results if r.status == STATUS_SKIPPED)
    failed = sum(1 for r in results if r.status == STATUS_FAILED)
    return InvestigationCycleResult(
        plan_results=tuple(results),
        succeeded=succeeded,
        skipped=skipped,
        failed=failed,
    )


def _execute_one(
    db: Session,
    plan: InvestigationPlan,
    settings: Settings,
    *,
    index_fn: AuthoritativeIndexIntegrateFn,
    busy_fn: BusyCheckFn,
) -> InvestigationPlanResult:
    if plan.action not in _SUPPORTED:
        return _skip(plan, REASON_UNSUPPORTED_ACTION)

    resolution = resolve_investigation_target(db, plan, settings)
    if resolution.reason is not None:
        return _skip(plan, resolution.reason)

    source = resolution.source
    assert source is not None
    url = (source.url or "").strip()

    if busy_fn():
        return InvestigationPlanResult(
            status=STATUS_SKIPPED,
            reason=REASON_INDEXING_BUSY,
            plan_id=plan.plan_id,
            source_id=source.id,
            url=url,
            downstream_result=None,
        )

    _dispatch = InvestigationDispatch(
        plan_id=plan.plan_id,
        verb=VERB_FETCH,
        source_id=int(source.id),
        url=url,
    )
    del _dispatch  # constructed for contract; not persisted

    try:
        downstream = index_fn(source)
    except KeyboardInterrupt:
        return InvestigationPlanResult(
            status=STATUS_FAILED,
            reason=REASON_INTERRUPTED,
            plan_id=plan.plan_id,
            source_id=source.id,
            url=url,
            downstream_result=None,
        )
    except Exception as exc:  # noqa: BLE001
        return InvestigationPlanResult(
            status=STATUS_FAILED,
            reason=_classify_exception(exc),
            plan_id=plan.plan_id,
            source_id=source.id,
            url=url,
            downstream_result=_opaque_exception(exc),
        )

    return _from_compose(plan, source, url, downstream)


def _from_compose(
    plan: InvestigationPlan,
    source: Source,
    url: str,
    downstream: Any,
) -> InvestigationPlanResult:
    """Map Index → Integrate compose outcome onto Step 060 vocabulary."""
    status_raw = str(getattr(downstream, "status", "") or "").strip().lower()
    outcome_raw = getattr(downstream, "outcome_reason", None)
    outcome = str(outcome_raw).strip() if outcome_raw is not None else ""
    opaque = _opaque_compose(downstream)

    if status_raw == COMPOSE_SUCCEEDED:
        return InvestigationPlanResult(
            status=STATUS_SUCCEEDED,
            reason=None,
            plan_id=plan.plan_id,
            source_id=source.id,
            url=url,
            downstream_result=opaque,
        )

    if status_raw == COMPOSE_SKIPPED:
        reason = _COMPOSE_REASON_MAP.get(outcome, REASON_CONTENT_UNCHANGED)
        return InvestigationPlanResult(
            status=STATUS_SKIPPED,
            reason=reason,
            plan_id=plan.plan_id,
            source_id=source.id,
            url=url,
            downstream_result=opaque,
        )

    if status_raw == COMPOSE_FAILED:
        reason = _COMPOSE_REASON_MAP.get(outcome, REASON_INDEX_FAILED)
        return InvestigationPlanResult(
            status=STATUS_FAILED,
            reason=reason,
            plan_id=plan.plan_id,
            source_id=source.id,
            url=url,
            downstream_result=opaque,
        )

    return InvestigationPlanResult(
        status=STATUS_FAILED,
        reason=REASON_INDEX_FAILED,
        plan_id=plan.plan_id,
        source_id=source.id,
        url=url,
        downstream_result=opaque,
    )


def _classify_exception(exc: BaseException) -> str:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "interrupt" in name or "interrupt" in msg:
        return REASON_INTERRUPTED
    if "fetch" in msg:
        return REASON_FETCH_FAILED
    if "parse" in msg or "extract" in msg:
        return REASON_PARSE_FAILED
    if "shadow" in msg or "memory" in msg:
        return REASON_MEMORY_SHADOW_WRITE_FAILED
    if "intelligence" in msg or msg.startswith("si"):
        return REASON_SI_FAILED
    return REASON_INDEX_FAILED


def _opaque_compose(downstream: Any) -> str:
    """Opaque non-secret summary from compose fields (already sanitized upstream)."""
    parts: list[str] = []
    status = str(getattr(downstream, "status", "") or "").strip()
    if status:
        parts.append(status)
    reason = getattr(downstream, "outcome_reason", None)
    if reason:
        parts.append(str(reason).strip())
    for attr in (
        "indexing_summary",
        "source_intelligence_summary",
        "memory_summary",
    ):
        value = getattr(downstream, attr, None)
        if value:
            parts.append(str(value).strip())
    return " | ".join(parts)


def _opaque_exception(exc: BaseException) -> str:
    # Type only — avoid placing raw exception text into summaries.
    return type(exc).__name__


def _skip(plan: InvestigationPlan, reason: str) -> InvestigationPlanResult:
    return InvestigationPlanResult(
        status=STATUS_SKIPPED,
        reason=reason,
        plan_id=plan.plan_id,
        source_id=None,
        url=None,
        downstream_result=None,
    )


def _default_busy_check() -> bool:
    from app.services.indexing_worker_service import indexing_worker
    from app.services.reprocess_worker_service import reprocess_worker
    from app.services.source_intelligence_worker_service import (
        source_intelligence_worker,
    )

    return bool(
        indexing_worker.is_running()
        or source_intelligence_worker.is_running()
        or reprocess_worker.is_running()
    )


def _default_index_integrate(db: Session, settings: Settings) -> AuthoritativeIndexIntegrateFn:
    """Bind the published Index → Integrate compose entrypoint."""

    def _call(source: Source) -> Any:
        from app.services.index_integrate import index_and_integrate

        return index_and_integrate(db, source, settings)

    return _call
