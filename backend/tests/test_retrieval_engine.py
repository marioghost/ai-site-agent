"""Tests for retrieval engine v3 components."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.chunk_fusion import ChunkFusionService
from app.services.retrieval_engine.document_quality import DocumentQualityService
from app.services.retrieval_engine.prompt_builder import CompactPromptBuilder
from app.services.retrieval_engine.semantic_expansion import SemanticExpansionService
from app.services.retrieval_intent_service import RetrievalIntentResult


def test_semantic_expansion_is_bounded():
    profile = KnowledgeProfile(
        organization_name="Example Corp",
        query_expansion_rules=[],
    )
    svc = SemanticExpansionService(profile, max_expansions=5)
    intent = RetrievalIntentResult(
        intent="entity_overview",
        legacy_intent="entity_overview",
        is_broad=True,
    )
    result = svc.expand("what do you know about the bank", intent_result=intent)
    assert len(result.terms) <= 10
    assert "example corp" in result.terms or "bank" in result.terms
    assert len(result.variants) <= 3
    assert result.strategy == "semantic"


def test_chunk_fusion_merges_neighbours():
    hits = [
        SearchHit(score=0.9, source_id=1, chunk_index=0, title="A", url="/a", source_type="page", text="Part one"),
        SearchHit(score=0.8, source_id=1, chunk_index=1, title="A", url="/a", source_type="page", text="Part two"),
        SearchHit(score=0.7, source_id=1, chunk_index=5, title="A", url="/a", source_type="page", text="Other"),
    ]
    fused = ChunkFusionService.fuse_source_chunks(hits, merge_neighbours=True, max_chunks=6)
    assert len(fused) == 2
    assert "Part one" in fused[0].text
    assert "Part two" in fused[0].text


def test_document_quality_penalizes_navigation():
    metrics = DocumentQualityService.estimate(
        text="Home Menu Footer Cookie policy navigation sidebar " * 20,
        boilerplate_ratio=0.6,
    )
    penalty = DocumentQualityService.ranking_penalty(metrics)
    assert penalty > 0.1
    assert metrics.quality_score < 0.8


def test_compact_prompt_is_shorter_than_legacy_style():
    hits = [
        SearchHit(
            score=0.9,
            source_id=1,
            chunk_index=0,
            title="About",
            url="https://example.com/about",
            source_type="page",
            text="We provide banking services.",
        )
    ]
    class _S:
        system_prompt = ""

    system, user = CompactPromptBuilder.build(
        message="What is this?",
        hits=hits,
        built_context=None,
        intent="entity_overview",
        settings=_S(),
        org_name="Example",
    )
    combined = len(system) + len(user)
    assert combined < 2500
    assert "Sources:" in user
    assert "Task:" not in user
    assert "AI-помічник цього вебсайту" in system
    assert "Sources" in system
    # Admin system_prompt is primary when set.
    settings_custom = type("S", (), {"system_prompt": "CUSTOM ADMIN SYSTEM PROMPT"})()
    system2, user2 = CompactPromptBuilder.build(
        message="What is this?",
        hits=hits,
        built_context=None,
        intent="entity_overview",
        settings=settings_custom,
        org_name="Example",
    )
    assert system2 == "CUSTOM ADMIN SYSTEM PROMPT"
    assert "Task:" not in user2
    assert "Question: What is this?" in user2
