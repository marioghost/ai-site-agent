"""Retrieval cache: store retrieved/reranked chunks keyed by normalized query.

Entries are invalidated lazily when namespace/version/TTL mismatches, or when
empty/no-context payloads are detected on read.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.cache import RetrievalCache
from app.services.cache_namespace_service import (
    RETRIEVAL_EMPTY_TTL_SECONDS,
    RETRIEVAL_ERROR_TTL_SECONDS,
    build_retrieval_namespace,
    namespace_hash,
)
from app.utils.hashing import sha256_hex
from app.utils.time_utils import is_expired, utcnow_naive

logger = get_logger(__name__)

RETRIEVAL_CACHE_TYPES = frozenset(
    {"retrieval_success", "retrieval_empty", "retrieval_error"}
)


@dataclass
class CachedRetrievalResult:
    chunks: list[dict]
    cache_type: str
    cache_key: str
    namespace_hash: str
    namespace: dict[str, str]
    selected_chunks_count: int
    context_used: bool
    age_seconds: int
    ttl_seconds: int
    negative_cache: bool = False


class RetrievalCacheService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def make_key(
        *,
        normalized_query: str,
        namespace: dict[str, str],
        top_k: int,
        similarity_threshold: float,
        qdrant_collection: str,
        rerank_enabled: bool,
        query_intent: str = "",
    ) -> str:
        ns_hash = namespace_hash(namespace)
        raw = "|".join(
            [
                normalized_query,
                ns_hash,
                str(top_k),
                f"{similarity_threshold:.4f}",
                qdrant_collection,
                str(bool(rerank_enabled)),
                query_intent,
            ]
        )
        return sha256_hex(raw)

    @staticmethod
    def build_namespace(settings, *, db: Session | None = None) -> dict[str, str]:
        return build_retrieval_namespace(settings, db=db)

    @staticmethod
    def namespace_hash(namespace: dict[str, str]) -> str:
        return namespace_hash(namespace)

    def get(
        self,
        cache_key: str,
        *,
        knowledge_version: int,
        namespace: dict[str, str],
    ) -> CachedRetrievalResult | None:
        ns_hash = namespace_hash(namespace)
        try:
            row = self.db.execute(
                select(RetrievalCache).where(RetrievalCache.cache_key == cache_key)
            ).scalar_one_or_none()
            if row is None:
                return None
            if row.knowledge_version != knowledge_version:
                self._delete(cache_key)
                return None
            if row.namespace_hash and row.namespace_hash != ns_hash:
                self._delete(cache_key)
                return None
            if is_expired(row.expires_at):
                self._delete(cache_key)
                return None

            try:
                data = json.loads(row.retrieved_chunks_json or "[]")
            except json.JSONDecodeError:
                logger.warning(
                    "Retrieval cache invalid JSON (key=%s…)", cache_key[:12]
                )
                self._delete(cache_key)
                return None
            if not isinstance(data, list):
                logger.warning(
                    "Retrieval cache payload not a list (key=%s…)", cache_key[:12]
                )
                self._delete(cache_key)
                return None

            chunk_count = row.selected_chunks_count or len(data)
            context_used = bool(row.context_used) and chunk_count > 0
            cache_type = row.cache_type or "retrieval_success"

            if chunk_count <= 0 or not data or not context_used:
                logger.info(
                    "Ignoring empty retrieval cache result (key=%s…, type=%s)",
                    cache_key[:12],
                    cache_type,
                )
                self._delete(cache_key)
                return None

            if cache_type == "retrieval_empty":
                logger.info(
                    "Ignoring negative retrieval cache entry (key=%s…)", cache_key[:12]
                )
                self._delete(cache_key)
                return None

            age_seconds = 0
            if row.created_at is not None:
                created = row.created_at
                if hasattr(created, "tzinfo") and created.tzinfo is not None:
                    created = created.replace(tzinfo=None)
                age_seconds = max(
                    0, int((utcnow_naive() - created).total_seconds())
                )
            ttl_seconds = 0
            if row.expires_at is not None and row.created_at is not None:
                expires = row.expires_at
                created = row.created_at
                if hasattr(expires, "tzinfo") and expires.tzinfo is not None:
                    expires = expires.replace(tzinfo=None)
                if hasattr(created, "tzinfo") and created.tzinfo is not None:
                    created = created.replace(tzinfo=None)
                ttl_seconds = max(0, int((expires - created).total_seconds()))

            return CachedRetrievalResult(
                chunks=data,
                cache_type=cache_type,
                cache_key=cache_key,
                namespace_hash=ns_hash,
                namespace=namespace,
                selected_chunks_count=chunk_count,
                context_used=context_used,
                age_seconds=age_seconds,
                ttl_seconds=ttl_seconds,
                negative_cache=cache_type in {"retrieval_empty", "retrieval_error"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Retrieval cache lookup failed (key=%s…): %s", cache_key[:12], exc
            )
            return None

    def store(
        self,
        *,
        cache_key: str,
        normalized_query: str,
        knowledge_version: int,
        namespace: dict[str, str],
        chunks: list[dict],
        ttl_seconds: int,
        cache_type: str = "retrieval_success",
    ) -> None:
        chunk_count = len(chunks)
        context_used = chunk_count > 0

        if cache_type == "retrieval_success" and (not chunks or chunk_count <= 0):
            logger.debug(
                "Skipping retrieval cache store for empty result (key=%s…)",
                cache_key[:12],
            )
            return

        if cache_type == "retrieval_empty":
            ttl_seconds = min(ttl_seconds, RETRIEVAL_EMPTY_TTL_SECONDS)
        elif cache_type == "retrieval_error":
            ttl_seconds = min(ttl_seconds, RETRIEVAL_ERROR_TTL_SECONDS)

        try:
            expires_at = utcnow_naive() + timedelta(seconds=max(1, ttl_seconds))
            ns_hash = namespace_hash(namespace)
            row = self.db.execute(
                select(RetrievalCache).where(RetrievalCache.cache_key == cache_key)
            ).scalar_one_or_none()
            payload = json.dumps(chunks, ensure_ascii=False)
            if row is None:
                row = RetrievalCache(
                    cache_key=cache_key,
                    normalized_query=normalized_query,
                    knowledge_version=knowledge_version,
                    namespace_hash=ns_hash,
                    cache_type=cache_type,
                    selected_chunks_count=chunk_count,
                    context_used=context_used,
                    retrieved_chunks_json=payload,
                    expires_at=expires_at,
                )
                self.db.add(row)
            else:
                row.normalized_query = normalized_query
                row.knowledge_version = knowledge_version
                row.namespace_hash = ns_hash
                row.cache_type = cache_type
                row.selected_chunks_count = chunk_count
                row.context_used = context_used
                row.retrieved_chunks_json = payload
                row.expires_at = expires_at
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Retrieval cache store failed (key=%s…): %s", cache_key[:12], exc
            )
            self.db.rollback()

    def invalidate_all(self) -> int:
        result = self.db.execute(delete(RetrievalCache))
        self.db.commit()
        return result.rowcount or 0

    def _delete(self, cache_key: str) -> None:
        try:
            self.db.execute(
                delete(RetrievalCache).where(RetrievalCache.cache_key == cache_key)
            )
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Retrieval cache delete failed (key=%s…): %s", cache_key[:12], exc
            )
            self.db.rollback()
