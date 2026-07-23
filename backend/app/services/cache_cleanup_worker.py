"""Background worker that deletes expired cache rows in batches."""
from __future__ import annotations

import threading
import time

from sqlalchemy import delete, select

from app.core.config import get_config
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.cache import AnswerCache, RetrievalCache
from app.models.source_intelligence_llm_cache import SourceIntelligenceLlmCache
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
                    logger.info("Cache cleanup removed %d expired row(s)", deleted)
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
            for model in (RetrievalCache, AnswerCache, SourceIntelligenceLlmCache):
                while True:
                    ids = list(
                        db.scalars(
                            select(model.id)
                            .where(model.expires_at.is_not(None))
                            .where(model.expires_at < now)
                            .order_by(model.id.asc())
                            .limit(batch_size)
                        ).all()
                    )
                    if not ids:
                        break
                    db.execute(delete(model).where(model.id.in_(ids)))
                    db.commit()
                    total += len(ids)
                    if len(ids) < batch_size:
                        break
                    time.sleep(0.01)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return total


cache_cleanup_worker = CacheCleanupWorker()
