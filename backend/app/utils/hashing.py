"""Hashing helpers used for deduplication and deterministic IDs."""
from __future__ import annotations

import hashlib
import uuid

# Stable namespace for generating deterministic chunk point IDs.
_CHUNK_NAMESPACE = uuid.UUID("4f1d2b3c-0a6e-4c1b-9f2a-1234567890ab")


def content_hash(text: str) -> str:
    """Return a stable SHA-256 hex digest for cleaned text content.

    Whitespace is normalised so trivially different whitespace does not
    produce a different hash.
    """
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sha256_hex(text: str) -> str:
    """Return a SHA-256 hex digest of the given text (no normalisation)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_point_id(source_id: int, chunk_index: int) -> str:
    """Return a deterministic UUID string for a chunk's Qdrant point id."""
    name = f"{source_id}:{chunk_index}"
    return str(uuid.uuid5(_CHUNK_NAMESPACE, name))
