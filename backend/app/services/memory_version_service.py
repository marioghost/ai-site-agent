"""Epistemic memory versioning.

``memory_version`` is a monotonically increasing integer stored on the settings
row. It tracks revisions to epistemic memory (claims, evidence, consolidation)
independently of ``knowledge_version``, which tracks indexed content changes
that affect retrieval caches.

**Sole authority:** only ``MemoryVersionService`` may read or write
``settings.memory_version``. Other modules must call this service; they must
not assign to the column directly.

Auto-bump integration (RFC-100 Step 031):
- Shadow claim integrate via ``EpistemicMemoryIntegrationService`` calls ``bump(commit=False)``
  so the version increment participates in the caller's DB transaction.

Other future bump owners:
- consolidation jobs
- memory schema migrations
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.repositories.settings_repository import SettingsRepository

logger = get_logger(__name__)


class MemoryVersionService:
    """Read and bump ``settings.memory_version``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> int:
        """Return the current memory version (minimum 1)."""
        settings = SettingsRepository(self.db).get_or_create()
        return self._coerce_version(settings)

    def ensure_initialized(self) -> int:
        """Ensure ``memory_version`` is at least 1; idempotent when already set."""
        repo = SettingsRepository(self.db)
        settings = repo.get_or_create()
        current = getattr(settings, "memory_version", None)
        if current is None or current < 1:
            settings.memory_version = 1
            repo.save(settings)
            logger.info("Memory version initialized to 1")
            return 1
        return int(current)

    def bump(self, *, commit: bool = True) -> int:
        """Increment memory version by exactly one and persist.

        When ``commit=False``, updates the settings row in the current session and
        ``flush()``es without committing. Use from shadow claim integration so a
        caller rollback discards the bump together with epistemic rows (Step 031).
        Manual admin bumps and standalone callers use the default ``commit=True``.
        """
        repo = SettingsRepository(self.db)
        settings = repo.get_or_create()
        settings.memory_version = self._coerce_version(settings) + 1
        if commit:
            repo.save(settings)
        else:
            self.db.add(settings)
            self.db.flush()
        logger.info("Memory version bumped to %d", settings.memory_version)
        return settings.memory_version

    @staticmethod
    def _coerce_version(settings: object) -> int:
        raw = getattr(settings, "memory_version", None)
        return raw if raw is not None and raw >= 1 else 1
