"""Knowledge Understanding API — read-only site understanding (Phase 0).

Path prefix avoids collision with Epistemic Health ``/api/understanding/*``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.user import User
from app.repositories.settings_repository import SettingsRepository
from app.schemas.knowledge_understanding import (
    ConceptSourcesResponse,
    KnowledgeUnderstandingSummaryResponse,
    UnderstandingConceptSummary,
    UnderstandingCoverageGap,
)
from app.services.knowledge_understanding.factory import get_understanding_layer

router = APIRouter(tags=["knowledge-understanding"])


@router.get(
    "/api/knowledge-understanding/summary",
    response_model=KnowledgeUnderstandingSummaryResponse,
)
def understanding_summary(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> KnowledgeUnderstandingSummaryResponse:
    settings = SettingsRepository(db).get_or_create()
    layer = get_understanding_layer(db, settings)
    summary = layer.summary()
    return KnowledgeUnderstandingSummaryResponse(
        enabled=summary.enabled,
        knowledge_version=summary.knowledge_version,
        snapshot_id=summary.snapshot_id,
        status=summary.status,
        representation=summary.representation,
        concept_count=summary.concept_count,
        evidence_count=summary.evidence_count,
        built_at=summary.built_at,
        build_duration_ms=summary.build_duration_ms,
        top_concepts=[
            UnderstandingConceptSummary(**c) for c in summary.top_concepts
        ],
        coverage_gaps=[UnderstandingCoverageGap(**g) for g in summary.coverage_gaps],
        error_message=summary.error_message,
        last_error_message=summary.last_error_message,
        last_error_at=summary.last_error_at,
    )


@router.get(
    "/api/knowledge-understanding/concepts/{concept_key}/sources",
    response_model=ConceptSourcesResponse,
)
def concept_sources(
    concept_key: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ConceptSourcesResponse:
    settings = SettingsRepository(db).get_or_create()
    layer = get_understanding_layer(db, settings)
    concept = layer.concept_by_key(concept_key)
    matches = layer.sources_for_concept(concept_key)[:limit]
    if concept is None and not matches:
        raise HTTPException(status_code=404, detail="concept_not_found")
    return ConceptSourcesResponse(
        concept_key=concept_key,
        label=concept.label if concept else None,
        sources=[
            {
                "source_id": m.source_id,
                "url": m.url,
                "title": m.title,
                "why": m.why,
                "understanding_score": m.understanding_score,
            }
            for m in matches
        ],
    )
