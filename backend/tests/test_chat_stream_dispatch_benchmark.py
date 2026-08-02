"""Optional dispatch overhead benchmarks — not part of release-check.

Run manually: see docs/PERFORMANCE_TESTS.md
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from tests.test_chat_stream_executive_routing import _golden_stream_events


@pytest.mark.benchmark
def test_stream_dispatch_overhead_executive(monkeypatch):
    """Wall-clock time to first stream event on Executive dispatch.

    Informational only — excluded from ``make release-check``. Structural routing
    parity is covered by ``test_chat_stream_executive_routing.py`` (unit tests).
    """
    from app.api.chat import _dispatch_stream_events

    golden = _golden_stream_events()

    class _FakeExecutive:
        def answer_stream(self, *args, **kwargs):
            return iter(golden)

    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )
    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: True)

    def _time_to_first() -> float:
        start = time.perf_counter()
        stream = _dispatch_stream_events(
            MagicMock(), MagicMock(), "q", "s", request_id="req-perf"
        )
        next(stream)
        return time.perf_counter() - start

    samples = 3
    times_ms = [_time_to_first() * 1000 for _ in range(samples)]
    times_ms.sort()
    median_ms = times_ms[len(times_ms) // 2]
    # Soft budget for manual runs — not enforced in CI release gate.
    assert median_ms < 50.0, (
        f"median first-event latency {median_ms:.1f}ms exceeds 50ms soft budget "
        "(investigate manually; not a release blocker)"
    )
