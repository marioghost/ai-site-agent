"""Persistent cache for LLM semantic Source Intelligence results."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.source_intelligence_llm_cache import SourceIntelligenceLlmCache
from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.source_intelligence_perf import (
    compute_llm_cache_key,
    compute_llm_prompt_hash,
    compute_profile_settings_hash,
)
from app.services.source_intelligence_constants import SOURCE_INTELLIGENCE_VERSION


class SourceIntelligenceLLMCacheService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def build_key(
        *,
        content_hash: str,
        llm_model: str,
        settings,
        language: str,
    ) -> str:
        return compute_llm_cache_key(
            content_hash=content_hash,
            llm_model=llm_model,
            prompt_hash=compute_llm_prompt_hash(),
            settings_hash=compute_profile_settings_hash(settings),
            language=language,
        )

    def get_profile(self, cache_key: str) -> SourceSemanticProfile | None:
        row = self.db.get(SourceIntelligenceLlmCache, cache_key)
        if row is None or row.status != "success":
            return None
        if row.expires_at and row.expires_at < datetime.now(timezone.utc):
            return None
        try:
            data = json.loads(row.semantic_json or "{}")
        except json.JSONDecodeError:
            return None
        if not data:
            return None
        return SourceSemanticProfile.model_validate(data)

    def store_success(
        self,
        *,
        cache_key: str,
        content_hash: str,
        llm_model: str,
        settings,
        language: str,
        raw_json: str,
        profile: SourceSemanticProfile,
        ttl_seconds: int | None = None,
    ) -> None:
        expires_at = None
        if ttl_seconds and ttl_seconds > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        row = self.db.get(SourceIntelligenceLlmCache, cache_key)
        if row is None:
            row = SourceIntelligenceLlmCache(cache_key=cache_key)
        row.content_hash = content_hash
        row.profile_version = SOURCE_INTELLIGENCE_VERSION
        row.llm_model = llm_model
        row.prompt_hash = compute_llm_prompt_hash()
        row.settings_hash = compute_profile_settings_hash(settings)
        row.language = language
        row.raw_json = raw_json
        row.semantic_json = json.dumps(profile.model_dump(), ensure_ascii=False)
        row.status = "success"
        row.error_message = None
        row.expires_at = expires_at
        self.db.add(row)

    def store_error(
        self,
        *,
        cache_key: str,
        content_hash: str,
        llm_model: str,
        settings,
        language: str,
        error_message: str,
    ) -> None:
        row = self.db.get(SourceIntelligenceLlmCache, cache_key)
        if row is None:
            row = SourceIntelligenceLlmCache(cache_key=cache_key)
        row.content_hash = content_hash
        row.profile_version = SOURCE_INTELLIGENCE_VERSION
        row.llm_model = llm_model
        row.prompt_hash = compute_llm_prompt_hash()
        row.settings_hash = compute_profile_settings_hash(settings)
        row.language = language
        row.raw_json = "{}"
        row.semantic_json = "{}"
        row.status = "error"
        row.error_message = (error_message or "")[:500]
        self.db.add(row)
