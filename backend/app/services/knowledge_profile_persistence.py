"""Persist Knowledge Profile with cache + reprocess side effects (single path)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.repositories.settings_repository import SettingsRepository
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.cache_invalidation_service import CacheInvalidationService
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.reprocess_service import mark_sources_needs_reprocess


def persist_knowledge_profile(
    db: Session,
    settings: Settings,
    profile: KnowledgeProfile,
    *,
    reason: str,
) -> Settings:
    """Save profile JSON, invalidate caches, and mark sources for reprocess."""
    settings.knowledge_profile_json = KnowledgeProfileService.to_json(profile)
    saved = SettingsRepository(db).save(settings)
    CacheInvalidationService(db, saved).invalidate_for_correctness(reason)
    mark_sources_needs_reprocess(db, reason=reason)
    return saved
