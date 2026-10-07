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
        embedding_matrix: object | None = None,
        embedding_keys: Sequence[str] | None = None,
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
        by_key = {c.concept_key: c for c in concepts}
        scored: list[tuple[float, Concept, str]] = []

        # Lexical pass (cheap).
        for concept in concepts:
            lexical = _lexical_score(concept, query_terms, understanding)
            if lexical >= 0.35:
                scored.append((lexical, concept, "lexical"))

        # Embedding pass — vectorized when matrix is available.
        embed_scores: dict[str, float] = {}
        if query_embedding and embedding_matrix is not None and embedding_keys:
            embed_scores = _vectorized_embed_scores(
                query_embedding, embedding_matrix, embedding_keys
            )
        elif query_embedding and embeddings:
            for key, concept_emb in embeddings.items():
                embed_scores[key] = cosine(query_embedding, concept_emb)

        for key, embed in embed_scores.items():
            if embed < EMBED_MATCH_THRESHOLD:
                continue
            concept = by_key.get(key)
            if concept is None:
                continue
            scored.append((embed, concept, "embedding"))

        # Keep best score per concept.
        best: dict[str, tuple[float, Concept, str]] = {}
        for score, concept, method in scored:
            prev = best.get(concept.concept_key)
            if prev is None or score > prev[0]:
                best[concept.concept_key] = (score, concept, method)

        ranked = sorted(best.values(), key=lambda t: t[0], reverse=True)[:MAX_RESOLVED]
        methods = {m for _, _, m in ranked}
        if "embedding" in methods and "lexical" in methods:
            resolution_method = "hybrid"
        elif "embedding" in methods:
            resolution_method = "embedding"
        elif "lexical" in methods:
            resolution_method = "lexical"
        else:
            resolution_method = "none"

        return ResolvedNeed(
            concepts=tuple(c for _, c, _ in ranked),
            need_type=_need_type(understanding),
            query_terms=query_terms,
            resolution_method=resolution_method,
        )


def _vectorized_embed_scores(
    query_embedding: Sequence[float],
    embedding_matrix: object,
    embedding_keys: Sequence[str],
) -> dict[str, float]:
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        return {}
    q = np.asarray(list(query_embedding), dtype=np.float32)
    qn = float(np.linalg.norm(q))
    if qn <= 0.0:
        return {}
    q = q / qn
    mat = embedding_matrix
    sims = mat @ q  # type: ignore[operator]
    out: dict[str, float] = {}
    for i, key in enumerate(embedding_keys):
        out[key] = float(sims[i])
    return out


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
