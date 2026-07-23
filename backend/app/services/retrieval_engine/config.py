"""Retrieval profile resolution — simple modes only, no user-facing score weights."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.settings import Settings


@dataclass(frozen=True)
class RetrievalProfileConfig:
    name: str
    top_k_dense: int
    top_k_lexical: int
    rerank_limit: int
    context_limit: int
    document_limit: int
    chunk_limit: int
    minimum_score: float


RETRIEVAL_PROFILES: dict[str, RetrievalProfileConfig] = {
    "automatic": RetrievalProfileConfig(
        name="automatic",
        top_k_dense=35,
        top_k_lexical=35,
        rerank_limit=18,
        context_limit=3,
        document_limit=3,
        chunk_limit=2,
        minimum_score=0.36,
    ),
    "fast": RetrievalProfileConfig(
        name="fast",
        top_k_dense=15,
        top_k_lexical=15,
        rerank_limit=8,
        context_limit=2,
        document_limit=2,
        chunk_limit=1,
        minimum_score=0.40,
    ),
    "balanced": RetrievalProfileConfig(
        name="balanced",
        top_k_dense=30,
        top_k_lexical=30,
        rerank_limit=15,
        context_limit=3,
        document_limit=3,
        chunk_limit=2,
        minimum_score=0.35,
    ),
    "high_precision": RetrievalProfileConfig(
        name="high_precision",
        top_k_dense=25,
        top_k_lexical=25,
        rerank_limit=10,
        context_limit=2,
        document_limit=2,
        chunk_limit=1,
        minimum_score=0.50,
    ),
    # Legacy aliases — map to modern modes
    "high_recall": RetrievalProfileConfig(
        name="high_recall",
        top_k_dense=50,
        top_k_lexical=50,
        rerank_limit=25,
        context_limit=5,
        document_limit=5,
        chunk_limit=3,
        minimum_score=0.25,
    ),
    "enterprise": RetrievalProfileConfig(
        name="enterprise",
        top_k_dense=40,
        top_k_lexical=40,
        rerank_limit=20,
        context_limit=4,
        document_limit=4,
        chunk_limit=2,
        minimum_score=0.38,
    ),
}


def load_retrieval_profile(settings: Settings) -> RetrievalProfileConfig:
    raw = getattr(settings, "retrieval_profile", None) or "automatic"
    name = str(raw).lower().strip() or "automatic"
    if name in {"quality", "high_quality"}:
        name = "high_precision"
    base = RETRIEVAL_PROFILES.get(name, RETRIEVAL_PROFILES["automatic"])
    return RetrievalProfileConfig(
        name=base.name,
        top_k_dense=int(getattr(settings, "top_k_dense", None) or base.top_k_dense),
        top_k_lexical=int(getattr(settings, "top_k_lexical", None) or base.top_k_lexical),
        rerank_limit=int(getattr(settings, "rerank_limit", None) or base.rerank_limit),
        context_limit=int(getattr(settings, "max_pages_in_context", None) or base.context_limit),
        document_limit=int(getattr(settings, "document_limit", None) or base.document_limit),
        chunk_limit=int(getattr(settings, "max_chunks_per_page", None) or base.chunk_limit),
        minimum_score=float(
            getattr(settings, "minimum_retrieval_score", None) or base.minimum_score
        ),
    )
