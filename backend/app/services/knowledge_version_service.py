"""Knowledge base versioning.

The knowledge version is a monotonically increasing integer stored on the
settings row. It is bumped whenever the indexed content changes in a way that
affects retrieval (full reindex, reindex-all, a source reindex that changed
content, or a source deletion). Caches compare against it to invalidate safely.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.repositories.settings_repository import SettingsRepository

logger = get_logger(__name__)


class KnowledgeVersionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> int:
        settings = SettingsRepository(self.db).get_or_create()
        return settings.knowledge_version or 1

    def bump(self) -> int:
        repo = SettingsRepository(self.db)
        settings = repo.get_or_create()
        settings.knowledge_version = (settings.knowledge_version or 1) + 1
        repo.save(settings)
        logger.info("Knowledge version bumped to %d", settings.knowledge_version)
        return settings.knowledge_version
