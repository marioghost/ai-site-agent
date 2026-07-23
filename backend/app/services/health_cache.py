"""Short-TTL cache for external subsystem health probes.

The dashboard polls ``/api/health`` and ``/api/system/performance`` frequently.
Probing Ollama and Qdrant live on every request adds load to subsystems that may
already be busy (e.g. Ollama during indexing), which made the Overview page show
spurious "Ollama error" whenever a probe was momentarily slow.

This cache serves the last successful probe for a few seconds and only re-probes
when the TTL expires, so transient slowness no longer flips the status and the
probe load stays bounded regardless of how many widgets poll.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.services.ollama_service import OllamaService
from app.services.qdrant_service import QdrantService

DEFAULT_TTL_SECONDS = 8.0


@dataclass
class _CachedHealth:
    ok: bool
    detail: str
    checked_at: float


class _HealthCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ollama: _CachedHealth | None = None
        self._qdrant: dict[str, _CachedHealth] = {}

    def ollama(self, ttl: float = DEFAULT_TTL_SECONDS) -> tuple[bool, str]:
        now = time.monotonic()
        with self._lock:
            cached = self._ollama
            if cached and (now - cached.checked_at) < ttl:
                return cached.ok, cached.detail
        ok, detail = OllamaService().health()
        with self._lock:
            # If the live probe failed but we have a recent good result, keep
            # reporting healthy briefly to avoid flapping under transient load.
            if not ok and self._ollama and self._ollama.ok:
                if (now - self._ollama.checked_at) < ttl * 2:
                    return True, self._ollama.detail
            self._ollama = _CachedHealth(ok=ok, detail=detail, checked_at=now)
        return ok, detail

    def qdrant(
        self, collection: str, ttl: float = DEFAULT_TTL_SECONDS
    ) -> tuple[bool, str]:
        now = time.monotonic()
        with self._lock:
            cached = self._qdrant.get(collection)
            if cached and (now - cached.checked_at) < ttl:
                return cached.ok, cached.detail
        ok, detail = QdrantService(collection=collection).health()
        with self._lock:
            if not ok:
                prev = self._qdrant.get(collection)
                if prev and prev.ok and (now - prev.checked_at) < ttl * 2:
                    return True, prev.detail
            self._qdrant[collection] = _CachedHealth(
                ok=ok, detail=detail, checked_at=now
            )
        return ok, detail


health_cache = _HealthCache()
