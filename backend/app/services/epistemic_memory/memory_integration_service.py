"""Memory Integration — sole owner of epistemic persistence (RFC-100 Step 030+).

Shadow ``memory_version`` bumps (Step 031): this module is the **only** automatic
caller of ``MemoryVersionService.bump()``. Bump runs only after a successful
``persist_claim_proposals`` when ``result.any_created`` is true, using
``bump(commit=False)`` so the increment shares the caller transaction.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.settings import Settings
from app.models.source import Source
from app.services.epistemic_memory.claim_extraction_from_si import ClaimExtractionFromSI
from app.services.epistemic_memory.epistemic_memory_service import EpistemicMemoryService
from app.services.epistemic_memory.shadow_persist_result import ShadowPersistResult
from app.services.feature_flags import memory_shadow_write_enabled
from app.services.memory_version_service import MemoryVersionService
from app.services.source_intelligence_service import SourceProfile

logger = get_logger(__name__)


class EpistemicMemoryIntegrationService:
    """Orchestrates SI → claim proposals → shadow persistence. Read-only when flag OFF."""

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def shadow_write_after_si(
        self, source: Source, profile: SourceProfile
    ) -> ShadowPersistResult | None:
        """Persist claim proposals after SI generation when ``memory_shadow_write_enabled``."""
        if not memory_shadow_write_enabled(self.settings):
            return None

        proposals = ClaimExtractionFromSI().extract_from_profile(source, profile)
        if not proposals:
            return ShadowPersistResult()

        result = EpistemicMemoryService(self.db).persist_claim_proposals(
            proposals,
            source=source,
            profile=profile,
        )
        if result.any_created:
            new_version = self._bump_after_successful_shadow_persist()
            logger.info(
                "Epistemic shadow write for source %s: obs=%d claims=%d links=%d memory_version=%d",
                source.id,
                result.observations_created,
                result.claims_created,
                result.evidence_links_created,
                new_version,
            )
        return result

    def _bump_after_successful_shadow_persist(self) -> int:
        """Single auto-bump path — only after persisted rows, deferred commit."""
        return MemoryVersionService(self.db).bump(commit=False)
