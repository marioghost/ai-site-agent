"""Agent Knowledge Profile API: read, update, presets, import/export."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.knowledge_profile_deprecation import apply_knowledge_profile_preset_load_deprecation
from app.api.deps import require_admin, require_authenticated
from app.core.database import get_db
from app.repositories.settings_repository import SettingsRepository
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.cache_invalidation_service import CacheInvalidationService
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.reprocess_service import mark_sources_needs_reprocess

router = APIRouter(prefix="/api/knowledge-profile", tags=["knowledge-profile"])


class KnowledgeProfileUpdate(BaseModel):
    profile: KnowledgeProfile


class KnowledgeProfileImport(BaseModel):
    profile: dict


class PresetLoadRequest(BaseModel):
    preset_id: str
    merge_identity: bool = False


@router.get("", response_model=KnowledgeProfile)
def get_profile(
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> KnowledgeProfile:
    settings = SettingsRepository(db).get_or_create()
    return KnowledgeProfileService.from_settings(settings)


@router.put("", response_model=KnowledgeProfile)
def update_profile(
    payload: KnowledgeProfileUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> KnowledgeProfile:
    errors = KnowledgeProfileService.validate_profile(payload.profile)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    repo = SettingsRepository(db)
    settings = repo.get_or_create()
    settings.knowledge_profile_json = KnowledgeProfileService.to_json(payload.profile)
    repo.save(settings)
    CacheInvalidationService(db, settings).invalidate_retrieval_cache(
        "knowledge_profile_updated"
    )
    mark_sources_needs_reprocess(db, reason="knowledge_profile_updated")
    return payload.profile


@router.get("/presets")
def list_presets(_user=Depends(require_authenticated)) -> list[dict[str, str]]:
    return KnowledgeProfileService.list_presets()


@router.post("/presets/load", response_model=KnowledgeProfile)
def load_preset(
    payload: PresetLoadRequest,
    response: Response,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> KnowledgeProfile:
    try:
        preset = KnowledgeProfileService.load_preset(payload.preset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preset not found") from exc
    if payload.merge_identity:
        current = KnowledgeProfileService.from_settings(SettingsRepository(db).get_or_create())
        preset.site_display_name = current.site_display_name or preset.site_display_name
        preset.organization_name = current.organization_name or preset.organization_name
        preset.organization_aliases = current.organization_aliases or preset.organization_aliases
        preset.site_subject = current.site_subject or preset.site_subject
        preset.entity_type = current.entity_type or preset.entity_type
    errors = KnowledgeProfileService.validate_profile(preset)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    repo = SettingsRepository(db)
    settings = repo.get_or_create()
    settings.knowledge_profile_json = KnowledgeProfileService.to_json(preset)
    repo.save(settings)
    CacheInvalidationService(db, settings).invalidate_retrieval_cache(
        "knowledge_profile_preset_loaded"
    )
    mark_sources_needs_reprocess(db, reason="knowledge_profile_preset_loaded")
    apply_knowledge_profile_preset_load_deprecation(response)
    return preset


@router.get("/export")
def export_profile(
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> dict:
    profile = KnowledgeProfileService.from_settings(SettingsRepository(db).get_or_create())
    return KnowledgeProfileService.export_profile(profile)


@router.post("/import", response_model=KnowledgeProfile)
def import_profile(
    payload: KnowledgeProfileImport,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> KnowledgeProfile:
    try:
        profile = KnowledgeProfileService.import_profile(payload.profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    repo = SettingsRepository(db)
    settings = repo.get_or_create()
    settings.knowledge_profile_json = json.dumps(payload.profile, ensure_ascii=False, indent=2)
    repo.save(settings)
    CacheInvalidationService(db, settings).invalidate_retrieval_cache(
        "knowledge_profile_imported"
    )
    mark_sources_needs_reprocess(db, reason="knowledge_profile_imported")
    return profile
