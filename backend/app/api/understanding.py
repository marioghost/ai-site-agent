"""Understanding API — read-only epistemic hypotheses (RFC-100 Step 035).

Exposes TensionSurfacingService results for admin inspection only.
No persistence, maintenance execution, investigation planning, chat, or
reasoning integration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.understanding import TensionListResponse, TensionRead
from app.services.epistemic_memory import EpistemicMemoryService
from app.services.tension_surfacing import TensionSurfacingService

router = APIRouter(tags=["understanding"])


@router.get("/api/understanding/tensions", response_model=TensionListResponse)
def list_tensions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    claim_limit: int | None = Query(
        None,
        ge=1,
        le=500,
        description="Max active claims to scan when surfacing hypotheses.",
    ),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TensionListResponse:
    """Return epistemic hypotheses (tensions) from Epistemic Memory.

    Each item is a possible-problem signal — not knowledge, belief, or fact.
    Results are computed in memory; nothing is written.
    """
    memory = EpistemicMemoryService(db)
    tensions = TensionSurfacingService(memory).surface_tensions(claim_limit=claim_limit)
    total = len(tensions)
    start = (page - 1) * page_size
    page_items = tensions[start : start + page_size]
    return TensionListResponse(
        items=[TensionRead.from_view(t) for t in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )
