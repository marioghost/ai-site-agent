"""Unit coverage for cooperative SI stop under a worker pool."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from app.services.source_intelligence_generation_service import (
    IntelligenceOptions,
    SourceIntelligenceGenerationService,
)

pytestmark = pytest.mark.unit


def test_pool_shutdown_cancels_pending_on_stop() -> None:
    """Regression: exiting `with ThreadPoolExecutor` waited for every future."""
    finished = 0

    def slow_work(_sid: int) -> None:
        nonlocal finished
        time.sleep(0.4)
        finished += 1

    pool = ThreadPoolExecutor(max_workers=2)
    try:
        futures = {pool.submit(slow_work, i): i for i in range(6)}
        for pending in futures:
            pending.cancel()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    time.sleep(0.15)
    assert finished < 6


def test_generation_service_run_respects_should_stop_before_pages() -> None:
    settings = MagicMock()
    settings.id = 1
    settings.source_intelligence_worker_count = 1
    db = MagicMock()
    svc = SourceIntelligenceGenerationService(db, settings)
    svc._perf_settings = MagicMock(  # type: ignore[method-assign]
        return_value={"page_size": 10, "db_batch_size": 10}
    )
    svc._resolve_worker_count = MagicMock(return_value=1)  # type: ignore[method-assign]
    svc.count_sources = MagicMock(return_value=3)  # type: ignore[method-assign]
    svc.iter_source_id_pages = MagicMock(return_value=iter([[1, 2, 3]]))  # type: ignore[method-assign]
    svc.finalize_generation = MagicMock()  # type: ignore[method-assign]

    result = svc.run(
        IntelligenceOptions(scope="all"),
        should_stop=lambda: True,
    )
    assert result.get("stopped") is True
    svc.finalize_generation.assert_not_called()
