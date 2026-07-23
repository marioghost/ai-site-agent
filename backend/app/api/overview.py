"""Overview dashboard API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_operator
from app.core.database import get_db
from app.schemas.overview import KnowledgeBaseStatus, OverviewResponse
from app.services.knowledge_base_metrics_service import KnowledgeBaseMetricsService

router = APIRouter(tags=["overview"])


@router.get("/api/overview", response_model=OverviewResponse)
def get_overview(
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> OverviewResponse:
    metrics = KnowledgeBaseMetricsService(db).compute()
    return OverviewResponse(
        knowledge_base=KnowledgeBaseStatus(**metrics.as_dict())
    )
