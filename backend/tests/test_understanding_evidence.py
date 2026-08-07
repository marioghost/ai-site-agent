"""Evidence Finder — knowledge need → source candidates + diagnostics."""
from __future__ import annotations

import pytest

from app.services.knowledge_understanding.diagnostics import build_understanding_trace
from app.services.knowledge_understanding.evidence_finder import EvidenceFinder
from app.services.knowledge_understanding.models import (
    Concept,
    EvidenceLink,
    ResolvedNeed,
)


pytestmark = pytest.mark.unit


def test_find_evidence_ranks_explains_and_canonical():
    concept = Concept(
        concept_key="getting-started",
        label="Getting started",
        aliases=(),
        confidence=0.9,
        evidence_count=2,
        canonical_source_id=10,
    )
    need = ResolvedNeed(
        concepts=(concept,),
        need_type="documentation",
        query_terms=("getting", "started"),
        resolution_method="lexical",
    )
    evidence = [
        EvidenceLink("getting-started", 10, "explains", 0.9, 0.9),
        EvidenceLink("getting-started", 11, "explains", 0.5, 0.5),
        EvidenceLink("getting-started", 12, "supports", 0.4, 0.4),
    ]
    matches = EvidenceFinder().find(
        need,
        evidence=evidence,
        concepts=[concept],
        source_meta={
            10: ("https://docs.example/start", "Getting Started"),
            11: ("https://docs.example/intro", "Intro"),
            12: ("https://docs.example/copy", "Copy"),
        },
    )
    assert matches
    assert matches[0].source_id == 10
    assert "canonical" in matches[0].why.lower() or "explains" in matches[0].why.lower()
    assert matches[0].understanding_score >= matches[-1].understanding_score


def test_understanding_trace_is_human_language():
    concept = Concept(
        concept_key="privacy-policy",
        label="Privacy policy",
        confidence=0.9,
        evidence_count=1,
        canonical_source_id=5,
    )
    need = ResolvedNeed(
        concepts=(concept,),
        need_type="documentation",
        resolution_method="lexical",
    )
    matches = EvidenceFinder().find(
        need,
        evidence=[EvidenceLink("privacy-policy", 5, "explains", 0.9, 0.9)],
        concepts=[concept],
        source_meta={5: ("https://corp.example/privacy", "Privacy")},
    )
    trace = build_understanding_trace(enabled=True, need=need, matches=matches)
    assert trace["enabled"] is True
    assert "Privacy policy" in trace["resolved_concepts"]
    assert trace["evidence_matches"]
    why = trace["evidence_matches"][0]["why"]
    assert "node" not in why.lower()
    assert "edge" not in why.lower()
    assert "graph" not in why.lower()
