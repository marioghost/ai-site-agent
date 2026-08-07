"""Understanding Resolver — QueryNeedInput → knowledge need."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from app.services.knowledge_understanding.models import Concept, QueryNeedInput, ResolvedNeed
from app.services.knowledge_understanding.similarity import cosine

_TOKEN_RE = re.compile(r"[\w\u0400-\u04FF]{2,}", re.UNICODE)
EMBED_MATCH_THRESHOLD = 0.72
MAX_RESOLVED = 12


class UnderstandingResolver:
    """Map a query into concepts the site understands."""

    def resolve(
        self,
        understanding: QueryNeedInput,
        concepts: Sequence[Concept],
        *,
        query_embedding: list[float] | None = None,
        concept_embeddings: Mapping[str, Sequence[float]] | None = None,
    ) -> ResolvedNeed:
        if not concepts:
            return ResolvedNeed(
                concepts=(),
                need_type=_need_type(understanding),
                query_terms=_query_terms(understanding),
                resolution_method="none",
            )

        query_terms = _query_terms(understanding)
        embeddings = concept_embeddings or {}
        scored: list[tuple[float, Concept, str]] = []

        for concept in concepts:
            lexical = _lexical_score(concept, query_terms, understanding)
            embed = 0.0
            concept_emb = embeddings.get(concept.concept_key)
            if query_embedding and concept_emb:
                embed = cosine(query_embedding, concept_emb)
            score = max(lexical, embed)
            if score <= 0.0:
                continue
            method = (
                "embedding"
                if embed >= lexical and embed >= EMBED_MATCH_THRESHOLD
                else "lexical"
            )
            if embed >= EMBED_MATCH_THRESHOLD or lexical >= 0.35:
                scored.append((score, concept, method))

        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:MAX_RESOLVED]
        methods = {m for _, _, m in top}
        if "embedding" in methods and "lexical" in methods:
            resolution_method = "hybrid"
        elif "embedding" in methods:
            resolution_method = "embedding"
        elif "lexical" in methods:
            resolution_method = "lexical"
        else:
            resolution_method = "none"

        return ResolvedNeed(
            concepts=tuple(c for _, c, _ in top),
            need_type=_need_type(understanding),
            query_terms=query_terms,
            resolution_method=resolution_method,
        )


def _need_type(understanding: QueryNeedInput) -> str:
    return (
        getattr(understanding, "expected_answer_type", None)
        or getattr(understanding, "semantic_focus", None)
        or getattr(understanding, "intent", None)
        or "general"
    )


def _query_terms(understanding: QueryNeedInput) -> tuple[str, ...]:
    parts = [
        getattr(understanding, "query", "") or "",
        getattr(understanding, "topic", None) or "",
        *list(getattr(understanding, "focus_terms", None) or []),
    ]
    tokens: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for tok in _TOKEN_RE.findall(part.lower()):
            if tok not in seen:
                seen.add(tok)
                tokens.append(tok)
    return tuple(tokens)


def _lexical_score(
    concept: Concept,
    query_terms: tuple[str, ...],
    understanding: QueryNeedInput,
) -> float:
    topic = (getattr(understanding, "topic", None) or "").strip()
    if not query_terms and not topic:
        return 0.0
    haystack = " ".join(
        [
            concept.label.lower(),
            *[a.lower() for a in concept.aliases],
        ]
    )
    concept_tokens = set(_TOKEN_RE.findall(haystack))
    if not concept_tokens:
        return 0.0
    overlap = concept_tokens & set(query_terms)
    if not overlap:
        topic_l = topic.lower()
        if topic_l and (topic_l in haystack or haystack in topic_l):
            return 0.55
        return 0.0
    return min(1.0, len(overlap) / max(2.0, min(len(concept_tokens), len(query_terms))))
