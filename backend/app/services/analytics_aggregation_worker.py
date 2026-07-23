"""Background worker for hourly analytics aggregation."""
from __future__ import annotations

import threading

from app.core.config import get_config
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.repositories.settings_repository import SettingsRepository
from app.services.analytics_aggregation_service import AnalyticsAggregationService

logger = get_logger(__name__)


class AnalyticsAggregationWorker:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="analytics-aggregation", daemon=True
        )
        self._thread.start()
        logger.info("Analytics aggregation worker started")

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        cfg = get_config()
        interval = max(5, cfg.analytics_aggregation_interval_minutes) * 60
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Analytics aggregation failed: %s", exc)
            self._stop.wait(interval)

    def run_once(self) -> int:
        db = SessionLocal()
        try:
            settings = SettingsRepository(db).get_or_create()
            fallback = settings.fallback_answer or ""
            return AnalyticsAggregationService(db).catch_up(fallback_answer=fallback)
        finally:
            db.close()


analytics_aggregation_worker = AnalyticsAggregationWorker()
