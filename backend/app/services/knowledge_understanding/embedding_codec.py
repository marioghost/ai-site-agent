"""Pack / unpack concept embeddings for LargeBinary columns."""
from __future__ import annotations

import struct


def pack_embedding(values: list[float] | tuple[float, ...] | None) -> bytes | None:
    if not values:
        return None
    return struct.pack(f"{len(values)}f", *[float(v) for v in values])


def unpack_embedding(blob: bytes | None) -> tuple[float, ...] | None:
    if not blob:
        return None
    n = len(blob) // 4
    if n <= 0 or len(blob) != n * 4:
        return None
    return struct.unpack(f"{n}f", blob)
