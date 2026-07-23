"""Unit tests for indexing status builder (progress, heartbeat, summary)."""
from __future__ import annotations

from datetime import timedelta

from app.services.indexing_progress import IndexingProgress
from app.services.indexing_status_builder import (
    compute_heartbeat_state,
    compute_run_progress,
    compute_run_summary,
)
from app.utils.time_utils import isoformat_now, utcnow


def test_progress_percent_when_selected_known():
    prog = IndexingProgress()
    prog.queue.queued_pages_for_this_run = 200
    prog.pages.processed_pages = 100
    run = compute_run_progress(prog)
    assert run.is_indeterminate is False
    assert run.percent == 50.0
    assert run.selected_total == 200
    assert run.processed_total == 100


def test_progress_indeterminate_when_selected_unknown():
    prog = IndexingProgress()
    prog.pages.processed_pages = 10
    run = compute_run_progress(prog)
    assert run.is_indeterminate is True
    assert run.percent is None


def test_heartbeat_active_slow_stuck():
    now = utcnow()
    active_ts = (now - timedelta(seconds=5)).isoformat() + "Z"
    slow_ts = (now - timedelta(seconds=45)).isoformat() + "Z"
    stuck_ts = (now - timedelta(seconds=400)).isoformat() + "Z"

    assert compute_heartbeat_state(active_ts, now=now)[0] == "active"
    assert compute_heartbeat_state(slow_ts, now=now)[0] == "slow"
    assert compute_heartbeat_state(stuck_ts, now=now)[0] == "stuck"


def test_summary_aggregates_outcomes():
    prog = IndexingProgress()
    prog.discovery.discovered_pages = 700
    prog.queue.queued_pages_for_this_run = 200
    prog.pages.processed_pages = 127
    prog.pages.indexed_new_pages = 120
    prog.pages.updated_pages = 3
    prog.pages.unchanged_pages = 4
    prog.pages.skipped_fresh_pages = 360
    prog.pages.failed_pages = 0
    summary = compute_run_summary(prog)
    assert summary.found_pages == 700
    assert summary.selected_pages == 200
    assert summary.processed_pages == 127
    assert summary.added == 120
    assert summary.updated == 3
    assert summary.unchanged == 4


def test_progress_records_activity():
    prog = IndexingProgress()
    prog.record_activity("Processing page: https://example.com/about")
    assert prog.heartbeat_counter == 1
    assert prog.last_activity_message == "Processing page: https://example.com/about"
    assert prog.last_activity_at is not None
