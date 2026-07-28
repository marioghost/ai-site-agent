"""Epistemic Health API — read-only epistemic hypotheses (RFC-100 Step 035).

Product name: Epistemic Health (formerly Understanding). Router path kept for
compatibility. No persistence, maintenance, chat, or reasoning integration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.user import User
from app.repositories.settings_repository import SettingsRepository
from app.schemas.understanding import (
    EpistemicHealthSummaryResponse,
    TensionListResponse,
    TensionRead,
)
from app.services.epistemic_memory import EpistemicMemoryService
from app.services.epistemic_memory.provenance_scope import (
    ProvenanceScope,
    parse_provenance_scope,
)
from app.services.feature_flags import memory_shadow_write_enabled
from app.services.memory_version_service import MemoryVersionService
from app.services.tension_surfacing import TensionSurfacingService

router = APIRouter(tags=["understanding"])


@router.get("/api/understanding/tensions", response_model=TensionListResponse)
@router.get("/api/epistemic-health/tensions", response_model=TensionListResponse)
def list_tensions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    claim_limit: int | None = Query(
        None,
        ge=1,
        le=500,
        description="Max active claims to scan when surfacing hypotheses.",
    ),
    provenance_scope: str = Query(
        "real",
        description="real | test | all. Default real excludes test fixtures.",
    ),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TensionListResponse:
    """Return epistemic hypotheses (tensions) from Epistemic Memory.

    Each item is a possible-problem signal — not knowledge, belief, or fact.
    Results are computed in memory; nothing is written.
    """
    try:
        scope = parse_provenance_scope(provenance_scope, default=ProvenanceScope.REAL)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    memory = EpistemicMemoryService(db)
    tensions = TensionSurfacingService(memory).surface_tensions(
        claim_limit=claim_limit,
        provenance_scope=scope,
    )
    total = len(tensions)
    start = (page - 1) * page_size
    page_items = tensions[start : start + page_size]
    return TensionListResponse(
        items=[TensionRead.from_view(t) for t in page_items],
        total=total,
        page=page,
        page_size=page_size,
        provenance_scope=scope.value,  # type: ignore[arg-type]
    )


@router.get(
    "/api/understanding/summary",
    response_model=EpistemicHealthSummaryResponse,
)
@router.get(
    "/api/epistemic-health/summary",
    response_model=EpistemicHealthSummaryResponse,
)
def epistemic_health_summary(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> EpistemicHealthSummaryResponse:
    """Live provenance-aware Epistemic Health statistics (read-only)."""
    memory = EpistemicMemoryService(db)
    split = memory.get_provenance_aware_summary()
    surfacing = TensionSurfacingService(memory)
    real_counts = surfacing.summarize_counts(provenance_scope=ProvenanceScope.REAL)
    test_counts = surfacing.summarize_counts(provenance_scope=ProvenanceScope.TEST)
    settings = SettingsRepository(db).get_or_create()
    return EpistemicHealthSummaryResponse(
        real_claims=split.real_claims,
        test_claims=split.test_claims,
        real_active_claims=split.real_active_claims,
        test_active_claims=split.test_active_claims,
        real_superseded_claims=split.real_superseded_claims,
        test_superseded_claims=split.test_superseded_claims,
        real_observations=split.real_observations,
        test_observations=split.test_observations,
        real_evidence_links=split.real_evidence_links,
        test_evidence_links=split.test_evidence_links,
        source_intelligence_claims=split.source_intelligence_claims,
        real_support_deficit_tensions=real_counts.support_deficit_tensions,
        real_conflict_tensions=real_counts.conflict_tensions,
        real_open_tensions=real_counts.open_tensions,
        test_open_tensions=test_counts.open_tensions,
        memory_version=MemoryVersionService(db).get(),
        memory_shadow_write_enabled=bool(memory_shadow_write_enabled(settings)),
        chat_impact="not_active",
        diagnostic_only=True,
        experimental=True,
    )
