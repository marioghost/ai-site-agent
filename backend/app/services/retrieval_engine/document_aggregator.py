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
            key=lambda d: DocumentAggregator._document_rank(d.all_chunks),
            reverse=True,
        )
        return documents, duplicates_removed

    @staticmethod
    def _best_chunk(chunks: list[SearchHit]) -> SearchHit:
        if len(chunks) == 1:
            return chunks[0]
        return max(
            chunks,
            key=lambda c: (
                DocumentAggregator._chunk_rank(c),
                len((c.text or "").strip()),
                bool((c.heading or "").strip()),
                c.dense_score,
                c.lexical_score,
            ),
        )

    @staticmethod
    def _document_rank(chunks: list[SearchHit]) -> float:
        ranked = sorted(
            (DocumentAggregator._chunk_rank(chunk) for chunk in chunks),
            reverse=True,
        )
        if not ranked:
            return 0.0
        best = ranked[0]
        support = sum(ranked[:3]) / min(3, len(ranked))
        coverage = min(0.08, 0.03 * max(0, len(ranked) - 1))
        return best * 0.72 + support * 0.28 + coverage

    @staticmethod
    def _chunk_rank(chunk: SearchHit) -> float:
        body_len = len((chunk.text or "").strip())
        richness = min(0.08, body_len / 2500.0)
        return (
            chunk.dense_score * 0.58
            + chunk.lexical_score * 0.34
            + richness
            + (0.03 if (chunk.heading or "").strip() else 0.0)
        )
