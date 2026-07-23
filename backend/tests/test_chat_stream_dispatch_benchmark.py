"""Optional dispatch overhead benchmarks — not part of release-check.

Run manually: see docs/PERFORMANCE_TESTS.md
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from tests.test_chat_stream_executive_routing import _golden_stream_events


@pytest.mark.benchmark
def test_stream_dispatch_overhead_legacy_vs_executive(monkeypatch):
    """Compare wall-clock time to first stream event: legacy vs executive dispatch.

    Informational only — excluded from ``make release-check``. Structural routing
    parity is covered by ``test_chat_stream_executive_routing.py`` (unit tests).
    """
    from app.api.chat import _dispatch_stream_events

    golden = _golden_stream_events()

    class _FakeStreaming:
        def iter_events(self, *args, **kwargs):
            return iter(golden)

    class _FakeExecutive:
        def answer_stream(self, *args, **kwargs):
            return iter(golden)

    monkeypatch.setattr("app.api.chat.RagStreamingService", lambda rag: _FakeStreaming())
    monkeypatch.setattr("app.api.chat.RagService", lambda db, settings: MagicMock())
    monkeypatch.setattr(
        "app.api.chat.ExecutiveService", lambda db, settings: _FakeExecutive()
    )

    def _time_to_first(*, executive: bool) -> float:
        monkeypatch.setattr(
            "app.api.chat.knowledge_os_executive_enabled", lambda: executive
        )
        start = time.perf_counter()
        stream = _dispatch_stream_events(
            MagicMock(), MagicMock(), "q", "s", request_id="req-perf"
        )
        next(stream)
        return time.perf_counter() - start

    samples = 3
    overhead_ms: list[float] = []
    for _ in range(samples):
        legacy_ms = _time_to_first(executive=False) * 1000
        executive_ms = _time_to_first(executive=True) * 1000
        overhead_ms.append(abs(executive_ms - legacy_ms))

    overhead_ms.sort()
    median_overhead = overhead_ms[len(overhead_ms) // 2]
    # Soft budget for manual runs — not enforced in CI release gate.
    assert median_overhead < 50.0, (
        f"median dispatch overhead {median_overhead:.1f}ms exceeds 50ms soft budget "
        "(investigate manually; not a release blocker)"
    )
