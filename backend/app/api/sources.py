"""Sources API: list, get, delete and reindex source documents."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import require_operator
from app.core.database import get_db
from app.repositories.settings_repository import SettingsRepository
from app.repositories.source_repository import SourceRepository
from app.schemas.common import MessageResponse
from app.schemas.source import (
    SourceBulkRequest,
    SourceDetailRead,
    SourceListResponse,
    SourceRead,
)
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.source_list_service import SourceListService
from app.services.source_repository_service import SourceRepositoryService

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=SourceListResponse)
def list_sources(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: str | None = Query(None),
    bucket: str | None = Query(None),
    search: str | None = Query(None),
    source_type: str | None = Query(None),
    url_contains: str | None = Query(None),
    date_range: str | None = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> SourceListResponse:
    items, total = SourceListService(db).list_sources(
        page=page,
        page_size=page_size,
        status=status,
        bucket=bucket,
        source_type=source_type,
        search=search,
        url_contains=url_contains,
        date_range=date_range,
    )
    return SourceListResponse(
        items=[SourceRead.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export")
def export_sources(
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> Response:
    items, _ = SourceListService(db).list_sources(page=1, page_size=10000)
    payload = json.dumps(items, ensure_ascii=False, indent=2, default=str)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=sources-export.json"},
    )


@router.get("/{source_id}", response_model=SourceDetailRead)
def get_source(
    source_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> SourceDetailRead:
    detail = SourceListService(db).get_detail(source_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceDetailRead.model_validate(detail)


@router.post("/bulk/reindex", response_model=MessageResponse)
def bulk_reindex(
    body: SourceBulkRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> MessageResponse:
    settings = SettingsRepository(db).get_or_create()
    svc = SourceRepositoryService(db, settings)
    repo = SourceRepository(db)
    count = 0
    for sid in body.ids:
        source = repo.get(sid)
        if source is None:
            continue
        source.content_hash = None
        repo.save(source)
        outcome = svc.reindex_source(source)
        if outcome.status == "indexed":
            count += 1
    if count:
        KnowledgeVersionService(db).bump()
    return MessageResponse(message=f"Reindexed {count} source(s)")


@router.post("/bulk/delete", response_model=MessageResponse)
def bulk_delete(
    body: SourceBulkRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> MessageResponse:
    settings = SettingsRepository(db).get_or_create()
    svc = SourceRepositoryService(db, settings)
    repo = SourceRepository(db)
    removed = 0
    for sid in body.ids:
        source = repo.get(sid)
        if source is None:
            continue
        svc.delete_source(source)
        removed += 1
    if removed:
        KnowledgeVersionService(db).bump()
    return MessageResponse(message=f"Deleted {removed} source(s)")


@router.post("/bulk/reset-status", response_model=MessageResponse)
def bulk_reset_status(
    body: SourceBulkRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> MessageResponse:
    repo = SourceRepository(db)
    reset = 0
    for sid in body.ids:
        source = repo.get(sid)
        if source is None:
            continue
        source.status = "pending"
        source.error_message = None
        repo.save(source)
        reset += 1
    return MessageResponse(message=f"Reset status for {reset} source(s)")


@router.delete("/{source_id}", response_model=MessageResponse)
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> MessageResponse:
    repo = SourceRepository(db)
    source = repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    settings = SettingsRepository(db).get_or_create()
    SourceRepositoryService(db, settings).delete_source(source)
    KnowledgeVersionService(db).bump()
    return MessageResponse(message="Source deleted")


@router.post("/{source_id}/reindex", response_model=SourceRead)
def reindex_source(
    source_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> SourceRead:
    repo = SourceRepository(db)
    source = repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    settings = SettingsRepository(db).get_or_create()
    source.content_hash = None
    repo.save(source)
    outcome = SourceRepositoryService(db, settings).reindex_source(source)
    if outcome.status == "indexed":
        KnowledgeVersionService(db).bump()
    db.refresh(source)
    detail = SourceListService(db).get_detail(source_id)
    return SourceRead.model_validate(detail or source)
