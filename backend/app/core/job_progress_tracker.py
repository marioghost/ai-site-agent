"""Throttled progress persistence for long-running background jobs."""
from __future__ import annotations

import time


class JobProgressThrottle:
    """Decide when to flush job progress to PostgreSQL.

    Persist only every N items or every X seconds, plus on forced events
    (start, completion, failure, manual stop).
    """

    def __init__(
        self,
        *,
        flush_every_items: int = 10,
        flush_interval_seconds: float = 3.0,
    ) -> None:
        self.flush_every_items = max(1, flush_every_items)
        self.flush_interval_seconds = max(0.5, flush_interval_seconds)
        self._since_flush = 0
        self._last_flush_at = 0.0
        self.flush_count = 0

    def should_flush(self, *, force: bool = False) -> bool:
        if force:
            return True
        self._since_flush += 1
        now = time.monotonic()
        if self._since_flush >= self.flush_every_items:
            return True
        if self._last_flush_at == 0.0:
            return True
        return (now - self._last_flush_at) >= self.flush_interval_seconds

    def mark_flushed(self) -> None:
        self._since_flush = 0
        self._last_flush_at = time.monotonic()
        self.flush_count += 1
