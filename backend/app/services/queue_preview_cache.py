"""Short-TTL cache for expensive queue-preview queries."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

DEFAULT_TTL_SECONDS = 20.0


@dataclass
class _Entry:
    data: dict[str, int]
    expires_at: float


class QueuePreviewCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entry: _Entry | None = None

    def get(self, key: tuple[Any, ...], ttl: float = DEFAULT_TTL_SECONDS) -> dict[str, int] | None:
        now = time.monotonic()
        with self._lock:
            entry = self._entry
            if entry is None or now >= entry.expires_at:
                return None
            if getattr(self, "_key", None) != key:
                return None
            return dict(entry.data)

    def set(self, key: tuple[Any, ...], data: dict[str, int], ttl: float = DEFAULT_TTL_SECONDS) -> None:
        with self._lock:
            self._key = key
            self._entry = _Entry(data=dict(data), expires_at=time.monotonic() + ttl)

    def invalidate(self) -> None:
        with self._lock:
            self._entry = None
            self._key = None


queue_preview_cache = QueuePreviewCache()
