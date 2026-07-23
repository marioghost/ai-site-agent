"""Retrieval service: embed query, search Qdrant, apply similarity threshold."""
from __future__ import annotations

from app.core.logging import get_logger
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService, SearchHit

logger = get_logger(__name__)


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        qdrant_service: QdrantService,
    ) -> None:
        self.embedding_service = embedding_service
        self.qdrant_service = qdrant_service

    def retrieve(
        self, query: str, top_k: int, similarity_threshold: float
    ) -> list[SearchHit]:
        """Return chunks whose similarity passes the threshold.

        This is the core no-hallucination guard: if nothing passes the
        threshold, the caller must NOT invoke the LLM.
        """
        vector = self.embedding_service.embed_query(query)
        hits = self.qdrant_service.search(vector, top_k=top_k)
        passing = [h for h in hits if h.score >= similarity_threshold]
        logger.info(
            "Retrieval: %d hits, %d passed threshold %.3f",
            len(hits),
            len(passing),
            similarity_threshold,
        )
        return passing
