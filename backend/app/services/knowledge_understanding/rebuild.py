"""Rebuild understanding after Source Intelligence indexing."""
from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from sqlalchemy import select, text
from sqlalchemy.orm import Session, load_only

from app.core.logging import get_logger
from app.models.settings import Settings
from app.models.source import Source
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_understanding.builder import UnderstandingBuilder
from app.services.knowledge_understanding.store import UnderstandingStore
from app.services.knowledge_version_service import KnowledgeVersionService

logger = get_logger(__name__)

EMBED_BATCH = 48
# Process-wide advisory lock key for understanding rebuild (Postgres).
# Prevents concurrent finalize/rebuild workers from interleaved persist+prune.
UNDERSTANDING_REBUILD_LOCK_KEY = 0x4B554C30  # 'KUL0'
EmbedFn = Callable[[list[str]], list[list[float]]]


class UnderstandingRebuildService:
    """Full rebuild of the concept-index understanding snapshot."""

    def __init__(
        self,
        db: Session,
        settings: Settings,
        *,
        embed_fn: EmbedFn | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self._embed_fn = embed_fn

    def rebuild_after_si(self) -> int | None:
        """Rebuild after SI batch finalize. Soft-fails; never blocks SI commit path fatally."""
        try:
            return self.rebuild()
        except Exception:  # noqa: BLE001
            logger.exception("Knowledge understanding rebuild failed after SI")
            try:
                self.db.rollback()
                kv = KnowledgeVersionService(self.db).get()
                UnderstandingStore(self.db).persist_error(
                    knowledge_version=kv,
                    build_duration_ms=0,
                    error_message="rebuild_after_si failed",
                )
                self.db.commit()
            except Exception:  # noqa: BLE001
                logger.exception("Failed to persist understanding error snapshot")
                self.db.rollback()
            return None

    def rebuild(self) -> int:
        from app.services.knowledge_understanding.builder import (
            BuiltUnderstanding,
            source_has_intelligence,
        )

        t0 = time.monotonic()
        self._acquire_rebuild_lock()
        knowledge_version = KnowledgeVersionService(self.db).get()
        sources = self._load_sources_for_understanding()
        store = UnderstandingStore(self.db)

        if not any(source_has_intelligence(s) for s in sources):
            latest = store.latest_ready()
            if (
                latest is not None
                and latest.knowledge_version == knowledge_version
                and latest.concept_count == 0
            ):
                return int(latest.id)
            duration_ms = int((time.monotonic() - t0) * 1000)
            snapshot = store.persist(
                BuiltUnderstanding(concepts=[], evidence=[]),
                knowledge_version=knowledge_version,
                build_duration_ms=duration_ms,
                status="ready",
            )
            self.db.commit()
            logger.info(
                "Understanding rebuilt (empty): snapshot=%s knowledge_version=%s",
                snapshot.id,
                knowledge_version,
            )
            return int(snapshot.id)

        embed_fn = self._embed_fn or self._default_embed_fn()
        builder = UnderstandingBuilder(embed_fn=embed_fn)
        built = builder.build(sources)
        duration_ms = int((time.monotonic() - t0) * 1000)
        snapshot = store.persist(
            built,
            knowledge_version=knowledge_version,
            build_duration_ms=duration_ms,
            status="ready",
        )
        self.db.commit()
        logger.info(
            "Understanding rebuilt: snapshot=%s concepts=%s evidence=%s "
            "sources_linked=%s/%s duration_ms=%s knowledge_version=%s",
            snapshot.id,
            snapshot.concept_count,
            snapshot.evidence_count,
            built.sources_linked,
            built.sources_total,
            duration_ms,
            knowledge_version,
        )
        return int(snapshot.id)

    def _acquire_rebuild_lock(self) -> None:
        """Serialize rebuilds on Postgres; no-op soft-fail on other dialects."""
        try:
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:k)"),
                {"k": UNDERSTANDING_REBUILD_LOCK_KEY},
            )
        except Exception:  # noqa: BLE001
            # SQLite/unit paths or missing advisory support — rebuild still proceeds.
            logger.debug("Understanding rebuild advisory lock unavailable", exc_info=True)

    def _load_sources_for_understanding(self) -> list[Source]:
        """Load only columns required for SI→understanding (not full page text)."""
        stmt = select(Source).options(
            load_only(
                Source.id,
                Source.title,
                Source.canonical,
                Source.content_hash,
                Source.intelligence_json,
            )
        )
        return list(self.db.scalars(stmt).all())

    def _default_embed_fn(self) -> EmbedFn:
        model = (getattr(self.settings, "embedding_model", None) or "").strip() or "bge-m3"
        service = EmbeddingService(model)

        def embed_fn(texts: Sequence[str]) -> list[list[float]]:
            if not texts:
                return []
            out: list[list[float]] = []
            batch: list[str] = []
            for text_item in texts:
                batch.append(text_item)
                if len(batch) >= EMBED_BATCH:
                    out.extend(service.embed_texts(batch, background=True))
                    batch = []
            if batch:
                out.extend(service.embed_texts(batch, background=True))
            return out

        return embed_fn
