"""Pure unit checks for analytics trend formatting (no Postgres)."""
from __future__ import annotations

import pytest

from app.services.analytics_service import _trend

pytestmark = pytest.mark.unit


def test_trend_caps_extreme_relative_change() -> None:
    spiked = _trend(43065, 151)
    assert spiked["change_pct"] == 999.0
    assert spiked["direction"] == "up"


def test_trend_empty_previous_is_bounded() -> None:
    empty_prev = _trend(100, 0)
    assert empty_prev["change_pct"] == 100.0
    assert empty_prev["direction"] == "up"


def test_trend_neutral_when_unchanged() -> None:
    flat = _trend(10, 10)
    assert flat["change_pct"] == 0.0
    assert flat["direction"] == "neutral"
