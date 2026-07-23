"""Embedding service. Thin orchestration over Ollama embeddings."""
from __future__ import annotations

from app.core.logging import get_logger
from app.services.ollama_service import OllamaError, OllamaService

logger = get_logger(__name__)


class EmbeddingService:
    def __init__(self, model: str, ollama: OllamaService | None = None) -> None:
        self.model = model
        self.ollama = ollama or OllamaService()

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (interactive — chat retrieval path)."""
        return self.ollama.embed(self.model, text)

    def embed_texts(
        self, texts: list[str], *, background: bool = True
    ) -> list[list[float]]:
        """Embed many texts (bulk indexing/reprocess path).

        Defaults to the background embedding pool so it never starves the
        interactive query-embedding slots used by live chat.
        """
        if not texts:
            return []
        try:
            return self.ollama.embed_batch(self.model, texts, background=background)
        except OllamaError as exc:
            logger.warning("Batch embed failed (%s); falling back to per-item", exc)
            vectors: list[list[float]] = []
            for text in texts:
                vectors.append(self.ollama.embed(self.model, text, background=background))
            return vectors

    def vector_size(self) -> int:
        """Probe the embedding model's vector dimension."""
        sample = self.embed_query("dimension probe")
        return len(sample)
