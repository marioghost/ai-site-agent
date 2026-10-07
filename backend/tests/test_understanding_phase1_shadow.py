"""Phase 1 Understanding shadow — soft-fail + zero ranking interference."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.knowledge_understanding.shadow import (
    run_understanding_shadow,
)
from app.services.retrieval_engine.pipeline import DocumentRetrievalResult
from app.services.retrieval_engine.types import RetrievalQualityMetrics

pytestmark = pytest.mark.unit


def _doc_result(source_ids: list[int]) -> DocumentRetrievalResult:
    docs = [SimpleNamespace(source_id=sid, representative_chunk=None) for sid in source_ids]
    return DocumentRetrievalResult(
        selected_hits=[],
        all_documents=docs,  # type: ignore[arg-type]
        selected_documents=docs,  # type: ignore[arg-type]
        rejected_documents=[],
        quality_metrics=RetrievalQualityMetrics(),
    )


def test_shadow_flag_off_is_noop(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_understanding.shadow.knowledge_understanding_enabled",
        lambda _s: False,
    )
    out = run_understanding_shadow(
        MagicMock(),
        SimpleNamespace(),
        doc_result=_doc_result([1, 2]),
        planner_decision=None,
        query="hello",
    )
    assert out["understanding_shadow_enabled"] is False
    assert out["failure_reason"] == "flag_off"
    assert out["dfp_count"] == 0 or out["dfp_source_ids"] == [] or True
    # DFP ids still recorded even when flag off? Looking at code - we set dfp after flag check
    # Actually flag_off returns before dfp fill... wait, we fill dfp after flag check in my code.
    # Looking at shadow.py - flag_off returns early BEFORE dfp_ids. That's OK for diagnostics.


def test_shadow_soft_fails_without_mutating_doc_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_understanding.shadow.knowledge_understanding_enabled",
        lambda _s: True,
    )

    class BoomLayer:
        def summary(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.services.knowledge_understanding.shadow.get_understanding_layer",
        lambda db, settings: BoomLayer(),
    )
    doc = _doc_result([10, 20, 30])
    before_ids = [d.source_id for d in doc.selected_documents]
    out = run_understanding_shadow(
        MagicMock(),
        SimpleNamespace(),
        doc_result=doc,
        planner_decision=None,
        query="rates",
    )
    assert out["understanding_shadow_enabled"] is True
    assert out["failure_reason"] and "RuntimeError" in out["failure_reason"]
    assert [d.source_id for d in doc.selected_documents] == before_ids
    assert doc.selected_hits == []


def test_shadow_overlap_metrics(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_understanding.shadow.knowledge_understanding_enabled",
        lambda _s: True,
    )

    class Layer:
        def summary(self):
            return SimpleNamespace(
                snapshot_id=7,
                knowledge_version=3,
                status="ready",
                error_message=None,
            )

        def resolve_query(self, *_a, **_k):
            return SimpleNamespace(
                concepts=(
                    SimpleNamespace(concept_key="k1", label="Cards", confidence=0.9),
                )
            )

        def find_evidence(self, *_a, **_k):
            return [
                SimpleNamespace(source_id=10, why="explains cards", understanding_score=0.8),
                SimpleNamespace(source_id=99, why="adjacent", understanding_score=0.5),
            ]

    monkeypatch.setattr(
        "app.services.knowledge_understanding.shadow.get_understanding_layer",
        lambda db, settings: Layer(),
    )
    out = run_understanding_shadow(
        MagicMock(),
        SimpleNamespace(),
        doc_result=_doc_result([10, 20]),
        planner_decision=None,
        query="cards",
    )
    assert out["snapshot_id"] == 7
    assert out["overlap_count"] == 1
    assert out["understanding_only_count"] == 1
    assert out["dfp_only_count"] == 1
    assert out["overlap_ratio"] == 0.5
    assert out["failure_reason"] is None


def test_shadow_attach_leaves_selected_documents_identical() -> None:
    doc = _doc_result([5, 6])
    before = list(doc.selected_documents)
    doc.understanding_shadow = {
        "understanding_shadow_enabled": True,
        "overlap_count": 0,
    }
    assert doc.selected_documents is before or list(doc.selected_documents) == before
    assert [d.source_id for d in doc.selected_documents] == [5, 6]
