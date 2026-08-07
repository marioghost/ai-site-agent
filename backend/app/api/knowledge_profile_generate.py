"""Knowledge Profile AI generation API."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_authenticated
from app.core.database import get_db
from app.repositories.profile_generation_job_repository import (
    ProfileGenerationJobRepository,
)
from app.repositories.settings_repository import SettingsRepository
from app.schemas.knowledge_profile_generation import (
    ApplyGeneratedProfileRequest,
    GenerateProfileRequest,
    GenerationPreview,
    ProfileGenerationJobStatus,
)
from app.services.knowledge_profile_generation_worker import (
    GenerationOptions,
    profile_generation_worker,
)
from app.services.knowledge_profile_service import KnowledgeProfileService

router = APIRouter(prefix="/api/knowledge-profile/generate", tags=["knowledge-profile"])


def _job_to_status(job) -> ProfileGenerationJobStatus:
    preview = None
    if job.result_json:
        try:
            preview = GenerationPreview.model_validate_json(job.result_json)
        except Exception:  # noqa: BLE001
            preview = None
    log_tail = []
    try:
        log_tail = json.loads(job.log_json or "[]")[-50:]
    except json.JSONDecodeError:
        pass
    analytics = {}
    try:
        analytics = json.loads(job.analytics_json or "{}")
    except json.JSONDecodeError:
        pass
    return ProfileGenerationJobStatus(
        id=job.id,
        status=job.status,
        current_stage=job.current_stage or "",
        progress_percent=job.progress_percent or 0,
        started_at=job.started_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
        error_message=job.error_message,
        preview=preview,
        log_tail=log_tail,
        analytics=analytics,
    )


@router.post("/start", response_model=ProfileGenerationJobStatus)
def start_generation(
    payload: GenerateProfileRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> ProfileGenerationJobStatus:
    if profile_generation_worker.is_running():
        raise HTTPException(status_code=409, detail="Generation already running")
    job_id = profile_generation_worker.start(
        GenerationOptions(
            use_llm=payload.use_llm,
            merge_identity=payload.merge_identity,
        )
    )
    job = ProfileGenerationJobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=500, detail="Job not created")
    return _job_to_status(job)


@router.get("/status", response_model=ProfileGenerationJobStatus)
def generation_status(
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> ProfileGenerationJobStatus:
    job = ProfileGenerationJobRepository(db).latest()
    if job is None:
        return ProfileGenerationJobStatus(id=0, status="idle")
    return _job_to_status(job)


@router.get("/{job_id}", response_model=ProfileGenerationJobStatus)
def get_generation_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> ProfileGenerationJobStatus:
    job = ProfileGenerationJobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_status(job)


@router.post("/apply", response_model=dict)
def apply_generated_profile(
    payload: ApplyGeneratedProfileRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> dict:
    errors = KnowledgeProfileService.validate_profile(payload.profile)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    repo = SettingsRepository(db)
    settings = repo.get_or_create()
    current = KnowledgeProfileService.from_settings(settings)
    merged = payload.profile
    sections = payload.sections or ["everything"]
    if "everything" not in sections:
        if "organization" not in sections:
            merged.organization_name = current.organization_name
            merged.site_display_name = current.site_display_name
            merged.organization_aliases = current.organization_aliases
            merged.site_subject = current.site_subject
            merged.entity_type = current.entity_type
        if "topics" not in sections:
            merged.important_topics = current.important_topics
        if "aliases" not in sections:
            merged.organization_aliases = current.organization_aliases
        if "query_patterns" not in sections:
            merged.overview_query_patterns = current.overview_query_patterns
        if "document_types" not in sections:
            merged.document_type_rules = current.document_type_rules
        if "retrieval_rules" not in sections:
            merged.source_priority_rules = current.source_priority_rules
        if "query_expansions" not in sections:
            merged.query_expansion_rules = current.query_expansion_rules
    from app.services.knowledge_profile_persistence import persist_knowledge_profile

    persist_knowledge_profile(
        db, settings, merged, reason="knowledge_profile_generated"
    )
    return {"message": "Profile applied", "profile": merged.model_dump()}


@router.get("/{job_id}/export-report")
def export_generation_report(
    job_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> dict:
    job = ProfileGenerationJobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    preview = None
    if job.result_json:
        preview = json.loads(job.result_json)
    return {
        "job_id": job.id,
        "status": job.status,
        "analytics": json.loads(job.analytics_json or "{}"),
        "preview": preview,
        "log": json.loads(job.log_json or "[]"),
    }
