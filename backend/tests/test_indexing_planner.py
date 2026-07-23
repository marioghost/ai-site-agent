"""Tests for priority-based indexing candidate planning."""
from __future__ import annotations

from datetime import timedelta

from app.models.source import Source
from app.services.indexing_planner_service import (
    CandidateClass,
    IndexingPlannerService,
)
from app.utils.time_utils import utcnow


def _source(
    *,
    url: str,
    status: str = "pending",
    next_refresh_at=None,
    source_type: str = "page",
) -> Source:
    return Source(
        url=url,
        status=status,
        source_type=source_type,
        next_refresh_at=next_refresh_at,
    )


def test_classify_new_pending_and_failed():
    planner = IndexingPlannerService(page_refresh_hours=24)
    now = utcnow()

    assert planner.classify(_source(url="https://a/new"), now=now) == CandidateClass.NEW
    assert (
        planner.classify(_source(url="https://a/failed", status="error"), now=now)
        == CandidateClass.FAILED
    )
    assert (
        planner.classify(_source(url="https://a/skipped", status="skipped"), now=now)
        == CandidateClass.SKIPPED
    )


def test_classify_stale_and_fresh_indexed():
    planner = IndexingPlannerService(page_refresh_hours=24)
    now = utcnow()

    fresh = _source(
        url="https://a/fresh",
        status="indexed",
        next_refresh_at=now + timedelta(hours=12),
    )
    stale = _source(
        url="https://a/stale",
        status="indexed",
        next_refresh_at=now - timedelta(hours=1),
    )
    missing_refresh = _source(url="https://a/no-refresh", status="indexed")

    assert planner.classify(fresh, now=now) == CandidateClass.FRESH
    assert planner.classify(stale, now=now) == CandidateClass.STALE
    assert planner.classify(missing_refresh, now=now) == CandidateClass.STALE


def test_should_process_skips_fresh_unless_forced():
    planner = IndexingPlannerService()
    forced = IndexingPlannerService(force_reindex=True)

    assert planner.should_process(CandidateClass.FRESH) is False
    assert planner.should_process(CandidateClass.NEW) is True
    assert forced.should_process(CandidateClass.FRESH) is True


def test_build_queue_sorts_by_priority():
    planner = IndexingPlannerService(page_refresh_hours=24)
    now = utcnow()

    sources = [
        _source(url="https://a/fresh", status="indexed", next_refresh_at=now + timedelta(hours=1)),
        _source(url="https://a/new"),
        _source(url="https://a/failed", status="error"),
        _source(
            url="https://a/stale",
            status="indexed",
            next_refresh_at=now - timedelta(hours=1),
        ),
    ]

    queue = planner.build_queue(sources, now=now)
    classes = [c.candidate_class for c in queue]

    assert CandidateClass.FRESH not in classes
    assert classes[0] == CandidateClass.NEW
    assert classes[1] == CandidateClass.FAILED
    assert classes[2] == CandidateClass.STALE


def test_force_reindex_includes_fresh_as_stale():
    planner = IndexingPlannerService(force_reindex=True, page_refresh_hours=24)
    now = utcnow()

    fresh = _source(
        url="https://a/fresh",
        status="indexed",
        next_refresh_at=now + timedelta(hours=12),
    )
    queue = planner.build_queue([fresh], now=now)

    assert len(queue) == 1
    assert queue[0].candidate_class == CandidateClass.STALE


def test_count_by_class():
    planner = IndexingPlannerService(page_refresh_hours=24)
    now = utcnow()

    sources = [
        _source(url="https://a/1"),
        _source(url="https://a/2", status="error"),
        _source(
            url="https://a/3",
            status="indexed",
            next_refresh_at=now + timedelta(hours=1),
        ),
    ]
    counts = planner.count_by_class(sources, now=now)

    assert counts["new"] == 1
    assert counts["failed"] == 1
    assert counts["fresh"] == 1


def _sources(count: int, *, status: str = "pending", prefix: str = "new") -> list[Source]:
    return [
        _source(url=f"https://example.com/{prefix}/{i}", status=status)
        for i in range(count)
    ]


def _fresh_sources(count: int, now) -> list[Source]:
    return [
        _source(
            url=f"https://example.com/fresh/{i}",
            status="indexed",
            next_refresh_at=now + timedelta(hours=12),
        )
        for i in range(count)
    ]


def test_new_pages_prioritized_over_fresh():
    planner = IndexingPlannerService(page_refresh_hours=24)
    now = utcnow()
    sources = _sources(500) + _fresh_sources(300, now)
    preview = planner.build_queue_preview(sources, max_pages_per_run=200, now=now)
    selected = planner.select_candidates_for_run(sources, max_pages_per_run=200, now=now)

    assert preview.new_pages_waiting == 500
    assert preview.fresh_pages_skipped_until_refresh == 300
    assert preview.queued_pages_for_this_run == 200
    assert len(selected) == 200
    assert all(c.candidate_class == CandidateClass.NEW for c in selected)


def test_second_run_continues_new_pages():
    planner = IndexingPlannerService(page_refresh_hours=24)
    now = utcnow()
    indexed = _fresh_sources(200, now)
    remaining_new = _sources(800, prefix="pending")
    sources = indexed + remaining_new
    preview = planner.build_queue_preview(sources, max_pages_per_run=200, now=now)
    selected = planner.select_candidates_for_run(sources, max_pages_per_run=200, now=now)

    assert preview.fresh_pages_skipped_until_refresh == 200
    assert preview.new_pages_waiting == 800
    assert len(selected) == 200
    assert all(c.candidate_class == CandidateClass.NEW for c in selected)


def test_stale_pages_after_new_exhausted():
    planner = IndexingPlannerService(page_refresh_hours=24)
    now = utcnow()
    sources = _sources(100) + [
        _source(
            url=f"https://example.com/stale/{i}",
            status="indexed",
            next_refresh_at=now - timedelta(hours=1),
        )
        for i in range(100)
    ]
    selected = planner.select_candidates_for_run(sources, max_pages_per_run=150, now=now)

    assert len(selected) == 150
    assert sum(1 for c in selected if c.candidate_class == CandidateClass.NEW) == 100
    assert sum(1 for c in selected if c.candidate_class == CandidateClass.STALE) == 50


def test_fresh_only_no_selection():
    planner = IndexingPlannerService(page_refresh_hours=24)
    now = utcnow()
    sources = _fresh_sources(300, now)
    preview = planner.build_queue_preview(sources, max_pages_per_run=200, now=now)
    selected = planner.select_candidates_for_run(sources, max_pages_per_run=200, now=now)

    assert preview.fresh_pages_skipped_until_refresh == 300
    assert preview.queued_pages_for_this_run == 0
    assert selected == []


def test_force_reindex_ignores_freshness():
    planner = IndexingPlannerService(force_reindex=True, page_refresh_hours=24)
    now = utcnow()
    sources = _fresh_sources(300, now)
    selected = planner.select_candidates_for_run(sources, max_pages_per_run=200, now=now)

    assert len(selected) == 200
    assert all(c.candidate_class == CandidateClass.STALE for c in selected)
