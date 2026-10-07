"""Process-local immutable cache for READY Understanding snapshots.

Phase 1 shadow creates a new layer per request; without caching, every query
reloads ~10k concepts + embeddings + evidence from Postgres (~1.5–2s).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from app.services.knowledge_understanding.models import Concept, EvidenceLink

_lock = threading.RLock()
_CACHE: dict[int, "SnapshotRuntime"] = {}
_MAX_ENTRIES = 2


@dataclass(frozen=True)
class SnapshotRuntime:
    snapshot_id: int
    knowledge_version: int
    concepts: tuple[Concept, ...]
    embeddings: dict[str, tuple[float, ...]]
    evidence: tuple[EvidenceLink, ...]
    source_meta: dict[int, tuple[str, str]]
    # Precomputed matrix for vectorized resolve (numpy ndarray | None).
    embedding_matrix: Any
    embedding_keys: tuple[str, ...]
    embedding_norms: Any


def get_cached(snapshot_id: int) -> SnapshotRuntime | None:
    with _lock:
        return _CACHE.get(snapshot_id)


def put_cached(runtime: SnapshotRuntime) -> SnapshotRuntime:
    with _lock:
        _CACHE[runtime.snapshot_id] = runtime
        if len(_CACHE) > _MAX_ENTRIES:
            # Drop oldest ids first.
            for sid in sorted(_CACHE.keys())[: len(_CACHE) - _MAX_ENTRIES]:
                if sid != runtime.snapshot_id:
                    _CACHE.pop(sid, None)
        return runtime


def clear_cache() -> None:
    with _lock:
        _CACHE.clear()
