"""Group chunk hits by document and pick the best representative chunk."""
from __future__ import annotations

from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.types import RankedDocument


class DocumentAggregator:
    """Convert chunk-level hits into one candidate per document (source)."""

    @staticmethod
    def aggregate(chunks: list[SearchHit]) -> tuple[list[RankedDocument], int]:
        by_source: dict[int, list[SearchHit]] = {}
        for chunk in chunks:
            by_source.setdefault(chunk.source_id, []).append(chunk)

        duplicates_removed = max(0, len(chunks) - len(by_source))
        documents: list[RankedDocument] = []

        for source_id, source_chunks in by_source.items():
            rep = DocumentAggregator._best_chunk(source_chunks)
            documents.append(
                RankedDocument(
                    source_id=source_id,
                    url=rep.url,
                    title=rep.title,
                    document_type=rep.document_type or "generic_page",
                    representative_chunk=rep,
                    all_chunks=sorted(source_chunks, key=lambda c: c.chunk_index),
                )
            )

        documents.sort(
            key=lambda d: max(
                d.representative_chunk.dense_score,
                d.representative_chunk.lexical_score,
            ),
            reverse=True,
        )
        return documents, duplicates_removed

    @staticmethod
    def _best_chunk(chunks: list[SearchHit]) -> SearchHit:
        return max(
            chunks,
            key=lambda c: (
                c.dense_score * 0.6 + c.lexical_score * 0.4,
                c.dense_score,
                c.lexical_score,
            ),
        )
