"""Tests for content hashing and deterministic point IDs."""
from __future__ import annotations

from app.utils.hashing import chunk_point_id, content_hash


def test_content_hash_is_stable():
    text = "The quick brown fox."
    assert content_hash(text) == content_hash(text)


def test_content_hash_ignores_whitespace_differences():
    a = content_hash("hello   world")
    b = content_hash("hello world")
    c = content_hash("hello \n world  ")
    assert a == b == c


def test_content_hash_changes_with_content():
    assert content_hash("hello world") != content_hash("hello there")


def test_chunk_point_id_is_deterministic():
    assert chunk_point_id(1, 0) == chunk_point_id(1, 0)
    assert chunk_point_id(1, 0) != chunk_point_id(1, 1)
    assert chunk_point_id(1, 0) != chunk_point_id(2, 0)
