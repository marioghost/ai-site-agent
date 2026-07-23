"""Integration-style planner scenario: 700 URLs, 360 fresh + 340 new."""
from __future__ import annotations

from datetime import timedelta

from app.models.source import Source
from app.services.indexing_planner_service import CandidateClass, IndexingPlannerService
from app.utils.time_utils import utcnow


def _source(url: str, *, status: str, next_refresh_at=None) -> Source:
    return Source(url=url, status=status, source_type="page", next_refresh_at=next_refresh_at)


def test_discovery_queue_scenario_700_mixed():
    now = utcnow()
    planner = IndexingPlannerService(page_refresh_hours=168)
    sources: list[Source] = []
    for i in range(360):
        sources.append(
            _source(
                f"https://site.example/fresh/{i}",
                status="indexed",
                next_refresh_at=now + timedelta(hours=72),
            )
        )
    for i in range(340):
        sources.append(_source(f"https://site.example/new/{i}", status="pending"))

    preview = planner.build_queue_preview(sources, max_pages_per_run=200, now=now)
    selected = planner.select_candidates_for_run(sources, max_pages_per_run=200, now=now)

    assert preview.new_pages_waiting == 340
    assert preview.fresh_pages_skipped_until_refresh == 360
    assert preview.queued_pages_for_this_run == 200
    assert preview.total_pages_waiting == 340
    assert len(selected) == 200
    assert all(c.candidate_class == CandidateClass.NEW for c in selected)
