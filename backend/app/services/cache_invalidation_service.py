"""Centralized cache invalidation for retrieval and answer caches."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.cache import AnswerCache, RetrievalCache
from app.models.settings import Settings
from app.repositories.settings_repository import SettingsRepository
from app.services.answer_cache_service import AnswerCacheService
from app.services.retrieval_cache_service import RetrievalCacheService

logger = get_logger(__name__)


class CacheInvalidationService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or SettingsRepository(db).get_or_create()

    def invalidate_retrieval_cache(self, reason: str) -> int:
        count = RetrievalCacheService(self.db).invalidate_all()
        logger.info("Retrieval cache invalidated: %s (%d rows)", reason, count)
        return count

    def invalidate_answer_cache(self, reason: str) -> None:
        AnswerCacheService(self.db, self.settings).invalidate_all()
        logger.info("Answer cache invalidated: %s", reason)

    def invalidate_all_caches(self, reason: str) -> int:
        retrieval_rows = self.invalidate_retrieval_cache(reason)
        self.invalidate_answer_cache(reason)
        return retrieval_rows

    @staticmethod
    def purge_poisoned_entries(db: Session, *, fallback_answer: str = "") -> dict[str, int]:
        """Remove empty retrieval cache rows and fallback answer cache rows."""
        stats = {"retrieval_empty": 0, "answer_fallback": 0, "retrieval_negative": 0}

        rows = list(db.scalars(select(RetrievalCache)).all())
        for row in rows:
            remove = False
            if row.cache_type in {"retrieval_empty", "retrieval_error"}:
                remove = True
                stats["retrieval_negative"] += 1
            elif (row.selected_chunks_count or 0) <= 0:
                remove = True
                stats["retrieval_empty"] += 1
            else:
                try:
                    import json

                    data = json.loads(row.retrieved_chunks_json or "[]")
                    if not isinstance(data, list) or len(data) == 0:
                        remove = True
                        stats["retrieval_empty"] += 1
                except Exception:  # noqa: BLE001
                    remove = True
                    stats["retrieval_empty"] += 1
            if remove:
                db.delete(row)

        fallback = (fallback_answer or "").strip()
        if not fallback:
            from app.repositories.settings_repository import DEFAULT_FALLBACK

            fallback = DEFAULT_FALLBACK
        answer_rows = list(db.scalars(select(AnswerCache)).all())
        for row in answer_rows:
            if not row.used_context or (
                row.answer_text and row.answer_text.strip() == fallback
            ):
                db.delete(row)
                stats["answer_fallback"] += 1

        if sum(stats.values()):
            db.commit()
            logger.info("Purged poisoned cache entries: %s", stats)
        return stats
