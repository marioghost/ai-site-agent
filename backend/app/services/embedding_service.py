"""Embedding service. Thin orchestration over Ollama embeddings."""
from __future__ import annotations

from collections.abc import Callable

from app.core.logging import get_logger
from app.services.ollama_service import OllamaError, OllamaService

logger = get_logger(__name__)

# Single source of truth for bulk embed chunking (indexing + understanding rebuild).
# Caps peak RAM for Ollama request bodies and returned float matrices — not a
# retrieval/ranking knob and not exposed to admins.
EMBED_BATCH = 48


class EmbeddingInterrupted(Exception):
    """Cooperative stop requested during batched embedding."""


class EmbeddingService:
    def __init__(self, model: str, ollama: OllamaService | None = None) -> None:
        self.model = model
        self.ollama = ollama or OllamaService()

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (interactive — chat retrieval path)."""
        return self.ollama.embed(self.model, text)

    def embed_texts(
        self,
        texts: list[str],
        *,
        background: bool = True,
        should_stop: Callable[[], bool] | None = None,
    ) -> list[list[float]]:
        """Embed many texts (bulk indexing/reprocess path).

        Defaults to the background embedding pool so it never starves the
        interactive query-embedding slots used by live chat. Sends texts in
        fixed-size batches to bound peak memory.
        """
        if not texts:
            return []
        out: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            if should_stop and should_stop():
                raise EmbeddingInterrupted()
            batch = texts[start : start + EMBED_BATCH]
            try:
                out.extend(
                    self.ollama.embed_batch(self.model, batch, background=background)
                )
            except EmbeddingInterrupted:
                raise
            except OllamaError as exc:
                logger.warning("Batch embed failed (%s); falling back to per-item", exc)
                for text in batch:
                    if should_stop and should_stop():
                        raise EmbeddingInterrupted()
                    out.append(
                        self.ollama.embed(self.model, text, background=background)
                    )
        return out

    def vector_size(self) -> int:
        """Probe the embedding model's vector dimension."""
        sample = self.embed_query("dimension probe")
        return len(sample)
