"""Job progress throttling tests."""
from __future__ import annotations

import pytest

from app.core.job_progress_tracker import JobProgressThrottle

pytestmark = pytest.mark.unit


def test_throttle_flushes_every_n_items():
    t = JobProgressThrottle(flush_every_items=3, flush_interval_seconds=999)
    assert t.should_flush() is True  # first tick
    t.mark_flushed()
    assert t.should_flush() is False
    assert t.should_flush() is False
    assert t.should_flush() is True
    t.mark_flushed()


def test_throttle_force_flush():
    t = JobProgressThrottle(flush_every_items=100, flush_interval_seconds=999)
    t.mark_flushed()
    assert t.should_flush() is False
    assert t.should_flush(force=True) is True
