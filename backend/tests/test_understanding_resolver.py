"""Understanding Resolver — query → knowledge need."""
from __future__ import annotations

import pytest

from app.services.knowledge_understanding.models import Concept
from app.services.knowledge_understanding.resolver import UnderstandingResolver
from app.services.retrieval_engine.query_understanding import QueryUnderstanding


pytestmark = pytest.mark.unit


def _qu(query: str, *, topic: str | None = None, focus: list[str] | None = None) -> QueryUnderstanding:
    return QueryUnderstanding(
        query=query,
        intent="documentation",
        legacy_intent="documentation",
        topic=topic,
        expected_answer_type="documentation",
        focus_terms=focus or [],
        confidence=0.8,
    )


def test_resolve_matches_concept_label():
    concepts = [
        Concept(
            concept_key="getting-started",
            label="Getting started",
            aliases=("setup", "install"),
            confidence=0.9,
            evidence_count=2,
        ),
        Concept(
            concept_key="privacy-policy",
            label="Privacy policy",
            aliases=("data protection",),
            confidence=0.95,
            evidence_count=1,
        ),
    ]
    need = UnderstandingResolver().resolve(
        _qu("How do I get started with setup?"),
        concepts,
    )
    assert need.concepts
    assert need.concepts[0].concept_key == "getting-started"
    assert need.resolution_method in {"lexical", "hybrid"}


def test_resolve_via_embedding_nearest_neighbor():
    concepts = [
        Concept(
            concept_key="api-auth",
            label="API authentication",
            aliases=(),
            confidence=0.9,
            evidence_count=1,
        ),
        Concept(
            concept_key="careers",
            label="Careers",
            aliases=(),
            confidence=0.8,
            evidence_count=1,
        ),
    ]
    need = UnderstandingResolver().resolve(
        _qu("token login flow"),
        concepts,
        query_embedding=[0.99, 0.01, 0.0],
        concept_embeddings={
            "api-auth": (1.0, 0.0, 0.0),
            "careers": (0.0, 1.0, 0.0),
        },
    )
    assert need.concepts
    assert need.concepts[0].concept_key == "api-auth"
    assert need.resolution_method in {"embedding", "hybrid"}
