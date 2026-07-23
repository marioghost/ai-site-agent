"""Slow query log sanitization."""
from __future__ import annotations

import pytest

from app.core.slow_query import _sanitize

pytestmark = pytest.mark.unit


def test_slow_query_redacts_secrets():
    sql = "SELECT * FROM users WHERE password='secret123' AND token=abc"
    out = _sanitize(sql)
    assert "secret123" not in out
    assert "***" in out
