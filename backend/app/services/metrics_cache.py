"""Short-TTL cache for expensive overview/knowledge-base metrics."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

DEFAULT_TTL_SECONDS = 30.0


@dataclass
class _Entry:
    data: dict[str, Any]
    expires_at: float


class MetricsCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entry: _Entry | None = None

    def get(self, ttl: float = DEFAULT_TTL_SECONDS) -> dict[str, Any] | None:
        now = time.monotonic()
        with self._lock:
            entry = self._entry
            if entry is None or now >= entry.expires_at:
                return None
            return dict(entry.data)

    def set(self, data: dict[str, Any], ttl: float = DEFAULT_TTL_SECONDS) -> None:
        with self._lock:
            self._entry = _Entry(data=dict(data), expires_at=time.monotonic() + ttl)

    def invalidate(self) -> None:
        with self._lock:
            self._entry = None


knowledge_metrics_cache = MetricsCache()
