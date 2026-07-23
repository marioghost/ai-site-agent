"""Build metadata API — release identity for operators (RFC-100 release hardening)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.build_info import BuildInfoResponse
from app.services.build_info_service import BuildInfoService

router = APIRouter(tags=["build"])


@router.get("/api/build", response_model=BuildInfoResponse)
def build_info(db: Session = Depends(get_db)) -> BuildInfoResponse:
    """Unauthenticated build/release snapshot (same visibility as /api/health)."""
    return BuildInfoResponse(**BuildInfoService(db).collect())
