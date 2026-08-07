"""Semantic answer cache.

Query embeddings for previously answered questions are stored in a dedicated
Qdrant collection; answer metadata lives in the ``answer_cache`` SQLite table.
A new question that is semantically very close to a cached one (and shares the
current knowledge version, and is not expired) is answered from cache without
calling the LLM.
"""
from __future__ import annotations

import json
import uuid
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.cache import AnswerCache
from app.models.settings import Settings
from app.services.qdrant_service import QdrantService
from app.utils.time_utils import is_expired, utcnow_naive

logger = get_logger(__name__)


def answer_cache_collection_name(qdrant_collection: str) -> str:
    return f"{qdrant_collection}_answer_cache"


class AnswerCacheService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.collection = answer_cache_collection_name(settings.qdrant_collection)
        self.qdrant = QdrantService(collection=self.collection)

    def lookup(
        self,
        query_vector: list[float],
        knowledge_version: int,
        similarity_threshold: float,
        *,
        namespace: dict[str, str] | None = None,
        fallback_answer: str = "",
    ) -> AnswerCache | None:
        """Return a usable cached answer row, or None on miss."""
        ns_hash = None
        if namespace is not None:
            from app.services.cache_namespace_service import namespace_hash as ns_hash_fn

            ns_hash = ns_hash_fn(namespace)
        fallback = (fallback_answer or "").strip()
        try:
            matches = self.qdrant.search_ids(query_vector, top_k=1)
            if not matches:
                return None
            point_id, score = matches[0]
            if score < similarity_threshold:
                return None
            row = self.db.execute(
                select(AnswerCache).where(AnswerCache.vector_id == point_id)
            ).scalar_one_or_none()
            if row is None:
                self.qdrant.delete_points([point_id])
                return None
            if row.knowledge_version != knowledge_version:
                self._delete_row(row)
                return None
            if ns_hash and row.namespace_hash and row.namespace_hash != ns_hash:
                self._delete_row(row)
                return None
            if is_expired(row.expires_at):
                self._delete_row(row)
                return None
            if not row.used_context:
                logger.info("Ignoring answer cache entry without context")
                self._delete_row(row)
                return None
            if fallback and row.answer_text.strip() == fallback:
                logger.info("Ignoring cached fallback answer")
                self._delete_row(row)
                return None
            if row.cache_type in {"answer_fallback", "answer_error"}:
                logger.info("Ignoring negative answer cache entry")
                self._delete_row(row)
                return None
            try:
                json.loads(row.sources_json or "[]")
            except json.JSONDecodeError:
                logger.warning(
                    "Answer cache invalid sources JSON (vector=%s…)", point_id[:12]
                )
                self._delete_row(row)
                return None
            return row
        except Exception as exc:  # noqa: BLE001
            logger.warning("Answer cache lookup failed: %s", exc)
            return None

    def store(
        self,
        *,
        normalized_query: str,
        query_text: str,
        query_vector: list[float],
        answer_text: str,
        sources_json: str,
        knowledge_version: int,
        ttl_seconds: int,
        namespace: dict[str, str] | None = None,
        used_context: bool = True,
        fallback_answer: str = "",
    ) -> None:
        if not query_vector:
            return
        fallback = (fallback_answer or "").strip()
        if not used_context:
            logger.debug("Skipping answer cache store for no-context result")
            return
        if fallback and answer_text.strip() == fallback:
            logger.debug("Skipping answer cache store for fallback answer")
            return

        from app.services.cache_namespace_service import namespace_hash as ns_hash_fn

        ns_hash = ns_hash_fn(namespace) if namespace else ""
        cache_type = "answer_success"
        point_id = str(uuid.uuid4())
        expires_at = utcnow_naive() + timedelta(seconds=max(1, ttl_seconds))
        try:
            self.qdrant.ensure_collection(len(query_vector), with_source_index=False)
            self.qdrant.upsert_chunks(
                [point_id],
                [query_vector],
                [
                    {
                        "knowledge_version": knowledge_version,
                        "normalized_query": normalized_query,
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to store answer-cache vector: %s", exc)
            return

        try:
            row = AnswerCache(
                vector_id=point_id,
                normalized_query=normalized_query,
                query_text=query_text,
                answer_text=answer_text,
                sources_json=sources_json,
                used_context=used_context,
                knowledge_version=knowledge_version,
                namespace_hash=ns_hash,
                cache_type=cache_type,
                expires_at=expires_at,
            )
            self.db.add(row)
            self.db.commit()
            self._enforce_capacity()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Answer cache store failed: %s", exc)
            self.db.rollback()

    def invalidate_all(self) -> None:
        """Drop all cached answers (rows + the Qdrant collection)."""
        self.db.execute(delete(AnswerCache))
        self.db.commit()
        self.qdrant.delete_collection()

    def purge_expired(self) -> int:
        """Remove expired answer-cache rows and their Qdrant points."""
        try:
            rows = list(self.db.execute(select(AnswerCache)).scalars().all())
            expired = [r for r in rows if is_expired(r.expires_at)]
            if not expired:
                return 0
            self.qdrant.delete_points([r.vector_id for r in expired])
            for r in expired:
                self.db.delete(r)
            self.db.commit()
            return len(expired)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Answer cache purge_expired failed: %s", exc)
            self.db.rollback()
            return 0

    def purge_stale_namespace(
        self, *, knowledge_version: int, namespace_hash: str
    ) -> int:
        """Delete rows (and Qdrant points) that no longer match the live namespace."""
        if not namespace_hash:
            return 0
        try:
            rows = list(self.db.scalars(select(AnswerCache)).all())
            stale = [
                r
                for r in rows
                if r.knowledge_version != knowledge_version
                or (r.namespace_hash and r.namespace_hash != namespace_hash)
            ]
            if not stale:
                return 0
            self.qdrant.delete_points([r.vector_id for r in stale])
            for r in stale:
                self.db.delete(r)
            self.db.commit()
            return len(stale)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Answer cache purge_stale_namespace failed: %s", exc)
            self.db.rollback()
            return 0

    def _enforce_capacity(self) -> None:
        limit = self.settings.max_cached_answers or 0
        if limit <= 0:
            return
        total = self.db.execute(
            select(func.count()).select_from(AnswerCache)
        ).scalar_one()
        if total <= limit:
            return
        overflow = total - limit
        old_rows = list(
            self.db.execute(
                select(AnswerCache).order_by(AnswerCache.created_at.asc()).limit(overflow)
            ).scalars().all()
        )
        if not old_rows:
            return
        self.qdrant.delete_points([r.vector_id for r in old_rows])
        for r in old_rows:
            self.db.delete(r)
        self.db.commit()

    def _delete_row(self, row: AnswerCache) -> None:
        try:
            self.qdrant.delete_points([row.vector_id])
            self.db.delete(row)
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Answer cache delete failed: %s", exc)
            self.db.rollback()
