"""Unit coverage for indexing cooperative stop and lean queue loading."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.embedding_service import EMBED_BATCH, EmbeddingInterrupted, EmbeddingService
from app.services.indexing_worker_service import IndexingWorker

pytestmark = pytest.mark.unit


def test_embed_texts_batches_and_respects_should_stop() -> None:
    ollama = MagicMock()
    ollama.embed_batch.side_effect = lambda _m, batch, background=True: [
        [0.0] * 3 for _ in batch
    ]
    svc = EmbeddingService(model="bge-m3", ollama=ollama)

    texts = [f"t{i}" for i in range(EMBED_BATCH + 5)]
    calls = {"n": 0}

    def stop_after_first_batch() -> bool:
        calls["n"] += 1
        # First check (before batch 1) continues; before batch 2 stops.
        return calls["n"] > 1

    with pytest.raises(EmbeddingInterrupted):
        svc.embed_texts(texts, should_stop=stop_after_first_batch)

    assert ollama.embed_batch.call_count == 1


def test_process_page_queue_stop_returns_true_and_finalizes_stopped() -> None:
    worker = IndexingWorker()
    worker._stop_event.set()

    job_repo = MagicMock()
    job = MagicMock()
    log = MagicMock()
    log.add = MagicMock()
    progress = MagicMock()
    progress.pages.processed_pages = 0
    progress.apply_queue_preview = MagicMock()
    progress.set_stage = MagicMock()
    progress.set_current_url = MagicMock()

    planner = MagicMock()
    preview = SimpleNamespace(
        new_pages_waiting=1,
        failed_pages_waiting=0,
        stale_pages_waiting=0,
        fresh_pages_skipped_until_refresh=0,
        queued_pages_for_this_run=1,
    )
    planner.build_queue_preview.return_value = preview
    source = SimpleNamespace(url="https://example.com/a", status="pending", source_type="page")
    planner.select_candidates_for_run.return_value = [
        SimpleNamespace(source=source, candidate_class=MagicMock())
    ]

    worker._persist_progress = MagicMock()  # type: ignore[method-assign]
    worker._finalize = MagicMock()  # type: ignore[method-assign]
    worker._source_url_type = MagicMock(return_value="page")  # type: ignore[method-assign]

    stopped = worker._process_page_queue(
        job_repo,
        job,
        log,
        progress,
        {"max_pages": 0, "force_reindex": False},
        planner,
        MagicMock(),
        MagicMock(),
        [source],
    )
    assert stopped is True
    worker._finalize.assert_called_once()
    assert worker._finalize.call_args.args[3] == "stopped"


def test_crawl_frontier_queued_membership_is_o1() -> None:
    from app.services.crawler_service import CrawlFrontier

    frontier = CrawlFrontier(allowed_domains=["example.com"], deny_patterns=[], max_depth=2)
    frontier.add("https://example.com/a", depth=0)
    frontier.add("https://example.com/a", depth=0)  # duplicate
    frontier.add("https://example.com/b", depth=0)
    assert frontier.has_next()
    first = frontier.pop()
    assert first is not None
    # Re-add after pop should work again
    frontier.add(first.url, depth=0)
    assert frontier.has_next()
