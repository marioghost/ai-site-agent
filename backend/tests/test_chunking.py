"""Tests for the chunking service."""
from __future__ import annotations

from app.services.chunking_service import ChunkingService


def test_short_text_single_chunk():
    service = ChunkingService(chunk_size=800, chunk_overlap=120)
    chunks = service.chunk("Short text content.")
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].text == "Short text content."


def test_empty_text_no_chunks():
    service = ChunkingService()
    assert service.chunk("") == []
    assert service.chunk("   \n  ") == []


def test_long_text_is_split_with_overlap():
    service = ChunkingService(chunk_size=100, chunk_overlap=20)
    text = " ".join(f"word{i}" for i in range(200))
    chunks = service.chunk(text)
    assert len(chunks) > 1
    # Indices are sequential starting from 0.
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # Each chunk respects the size bound (roughly, allowing word boundaries).
    for c in chunks:
        assert len(c.text) <= 100


def test_chunking_is_deterministic():
    text = " ".join(f"token{i}" for i in range(500))
    a = ChunkingService(chunk_size=200, chunk_overlap=40).chunk(text)
    b = ChunkingService(chunk_size=200, chunk_overlap=40).chunk(text)
    assert [c.text for c in a] == [c.text for c in b]


def test_overlap_clamped_when_too_large():
    # overlap >= size should be clamped, not loop forever.
    service = ChunkingService(chunk_size=50, chunk_overlap=100)
    chunks = service.chunk(" ".join(f"w{i}" for i in range(100)))
    assert len(chunks) >= 1
