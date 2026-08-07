"""Concept normalizer — embedding alias merge, no domain synonym tables."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services.knowledge_understanding.normalizer import (
    ConceptNormalizer,
    RawConcept,
    should_merge_labels,
)
from app.services.knowledge_understanding.similarity import cosine


pytestmark = pytest.mark.unit


def _embed(texts: list[str]) -> list[list[float]]:
    """Near-duplicates share almost the same vector; unrelated diverge."""
    out = []
    for text in texts:
        t = (text or "").lower().strip()
        if "onboarding" in t or "getting started" in t or "get started" in t:
            base = [1.0, 0.0, 0.0, 0.0]
        elif "api" in t and "auth" in t:
            base = [0.0, 1.0, 0.0, 0.0]
        elif "privacy" in t:
            base = [0.0, 0.0, 1.0, 0.0]
        else:
            base = [0.0, 0.0, 0.0, 1.0]
            for i, ch in enumerate(t[:8]):
                base[i % 4] += (ord(ch) % 17) / 50.0
        n = sum(v * v for v in base) ** 0.5 or 1.0
        out.append([v / n for v in base])
    return out


def test_alias_merge_by_embedding_similarity():
    raw = [
        RawConcept(label="Getting started", confidence=0.9, source_id=1),
        RawConcept(label="Onboarding guide", confidence=0.8, source_id=2),
        RawConcept(label="Privacy policy", confidence=0.95, source_id=3),
    ]
    concepts = ConceptNormalizer(embed_fn=_embed, merge_threshold=0.88).normalize(raw)
    labels = {c.label for c in concepts}
    assert len(concepts) == 2
    assert "Privacy policy" in labels
    merged = next(c for c in concepts if c.label != "Privacy policy")
    assert len(merged.members) >= 2


def test_exact_label_merge_preserves_all_sources():
    raw = [
        RawConcept(
            label="API authentication",
            confidence=0.7,
            source_id=1,
            relation="explains",
        ),
        RawConcept(
            label="API authentication",
            confidence=0.9,
            source_id=2,
            relation="explains",
        ),
    ]
    concepts = ConceptNormalizer(embed_fn=_embed).normalize(raw)
    assert len(concepts) == 1
    member_ids = {m.source_id for m in concepts[0].members}
    assert member_ids == {1, 2}


def test_short_labels_without_shared_tokens_do_not_merge():
    # Distinct single-token labels must never fuzzy-merge.
    assert should_merge_labels("rates", "dates", 0.99) is False
    assert should_merge_labels("Getting started", "Onboarding guide", 0.99) is True
    assert should_merge_labels("Privacy policy", "Privacy policy", 0.5) is True


def test_cosine_identical_vectors():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_normalizer_module_has_no_domain_synonym_tables():
    src_path = Path(__file__).resolve().parents[1] / (
        "app/services/knowledge_understanding/normalizer.py"
    )
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    banned_names = {"SYNONYMS", "ALIAS_MAP", "DOMAIN_ALIASES", "BANK_TERMS", "INDUSTRY"}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in banned_names:
                    raise AssertionError(f"forbidden synonym table: {target.id}")
