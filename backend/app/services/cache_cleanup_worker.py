"""Background worker that deletes expired cache rows and stale answer vectors."""
from __future__ import annotations

import threading
import time

from sqlalchemy import delete, select

from app.core.config import get_config
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.cache import AnswerCache, RetrievalCache
from app.models.source_intelligence_llm_cache import SourceIntelligenceLlmCache
from app.repositories.settings_repository import SettingsRepository
from app.services.answer_cache_service import AnswerCacheService
from app.services.cache_namespace_service import build_retrieval_namespace, namespace_hash
from app.utils.time_utils import utcnow

logger = get_logger(__name__)


class CacheCleanupWorker:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="cache-cleanup", daemon=True
        )
        self._thread.start()
        logger.info("Cache cleanup worker started")

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        cfg = get_config()
        interval = max(5, cfg.cache_cleanup_interval_minutes) * 60
        while not self._stop.is_set():
            try:
                deleted = self.run_once()
                if deleted:
                    logger.info("Cache cleanup removed %d expired/stale row(s)", deleted)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Cache cleanup failed: %s", exc)
            self._stop.wait(interval)

    def run_once(self) -> int:
        cfg = get_config()
        batch_size = max(100, cfg.cache_cleanup_batch_size)
        now = utcnow()
        total = 0
        db = SessionLocal()
        try:
            total += self._purge_expired_by_pk(
                db, RetrievalCache, pk_attr="id", batch_size=batch_size, now=now
            )
            # Answer: expire via service so Qdrant points are removed too.
            settings = SettingsRepository(db).get_or_create()
            answer_svc = AnswerCacheService(db, settings)
            total += answer_svc.purge_expired()
            try:
                ns = build_retrieval_namespace(settings, db=db)
                total += answer_svc.purge_stale_namespace(
                    knowledge_version=int(settings.knowledge_version or 1),
                    namespace_hash=namespace_hash(ns),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Answer stale-namespace sweep skipped: %s", exc)

            total += self._purge_expired_by_pk(
                db,
                SourceIntelligenceLlmCache,
                pk_attr="cache_key",
                batch_size=batch_size,
                now=now,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return total

    @staticmethod
    def _purge_expired_by_pk(
        db,
        model,
        *,
        pk_attr: str,
        batch_size: int,
        now,
    ) -> int:
        pk_col = getattr(model, pk_attr)
        total = 0
        while True:
            keys = list(
                db.scalars(
                    select(pk_col)
                    .where(model.expires_at.is_not(None))
                    .where(model.expires_at < now)
                    .order_by(pk_col.asc())
                    .limit(batch_size)
                ).all()
            )
            if not keys:
                break
            db.execute(delete(model).where(pk_col.in_(keys)))
            db.commit()
            total += len(keys)
            if len(keys) < batch_size:
                break
            time.sleep(0.01)
        return total


cache_cleanup_worker = CacheCleanupWorker()
