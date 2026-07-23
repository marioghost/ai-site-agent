"""Dense and lexical chunk retrievers — no document-level scoring."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.chunk import Chunk
from app.models.settings import Settings
from app.models.source import Source
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.content_signals import normalize_content_hint, token_set
from app.services.content_category_service import detect_content_category
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.lexical_index_service import LexicalIndexService
from app.services.qdrant_service import QdrantService, SearchHit
from app.services.query_expansion_service import QueryExpansionService

logger = get_logger(__name__)


def _chunk_key(source_id: int, chunk_index: int) -> str:
    return f"{source_id}:{chunk_index}"


@dataclass
class ChunkRetrievalDebug:
    normalized_query: str = ""
    variants: list[str] = field(default_factory=list)
    match_query: str = ""
    mode: str = "hybrid"
    dense_count: int = 0
    lexical_count: int = 0
    merged_count: int = 0

    def to_dict(self) -> dict:
        return {
            "normalized_query": self.normalized_query,
            "variants": self.variants,
            "match_query": self.match_query,
            "mode": self.mode,
            "dense_count": self.dense_count,
            "lexical_count": self.lexical_count,
            "merged_count": self.merged_count,
        }


class EmbeddingRetriever:
    """Dense vector search via Qdrant."""

    def __init__(self, embedding: EmbeddingService, qdrant: QdrantService) -> None:
        self.embedding = embedding
        self.qdrant = qdrant

    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        query_vector: list[float] | None = None,
    ) -> list[SearchHit]:
        try:
            if query_vector is None:
                query_vector = self.embedding.embed_query(query)
            hits = self.qdrant.search(query_vector, top_k=top_k)
            for hit in hits:
                hit.dense_score = max(0.0, min(1.0, hit.score))
            return hits
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dense retrieval failed: %s", exc)
            return []


class LexicalRetriever:
    """PostgreSQL FTS chunk search."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.lexical = LexicalIndexService(db)

    @property
    def enabled(self) -> bool:
        return self.lexical.enabled

    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        expansion_terms: list[str] | None = None,
        profile: KnowledgeProfile | None = None,
        query_intent: str = "unknown",
        enable_expansion: bool = True,
    ) -> tuple[list[SearchHit], str, list[str]]:
        if not self.enabled:
            return [], "", []
        if expansion_terms:
            terms = list(dict.fromkeys(expansion_terms))
        elif enable_expansion and profile:
            expander = QueryExpansionService(profile)
            terms = expander.expanded_terms(query, intent=query_intent)
        else:
            terms = list(token_set(query))
        match_query = LexicalIndexService.build_match_query(terms, phrase=query)
        rows = self.lexical.search(match_query, top_k=top_k)
        hits = self._rows_to_hits(rows)
        lex_count = len(hits)
        for i, hit in enumerate(hits):
            hit.lexical_score = (lex_count - i) / lex_count if lex_count else 0.0
        return hits, match_query, terms

    def _rows_to_hits(self, rows: list[tuple[int, int, float]]) -> list[SearchHit]:
        if not rows:
            return []
        chunk_ids = [cid for cid, _sid, _r in rows]
        chunk_map = {
            c.id: c
            for c in self.db.execute(
                select(Chunk).where(Chunk.id.in_(chunk_ids))
            ).scalars().all()
        }
        hits: list[SearchHit] = []
        for cid, sid, _rank in rows:
            c = chunk_map.get(cid)
            if c is None:
                continue
            hits.append(
                SearchHit(
                    score=0.0,
                    source_id=sid,
                    chunk_index=c.chunk_index,
                    title=c.title or "",
                    url=c.url or "",
                    source_type=c.source_type or "page",
                    text=c.text or "",
                    heading=c.heading or "",
                    is_homepage=bool(c.is_homepage),
                    is_structured_block=bool(c.is_structured_block),
                    content_type_hint=normalize_content_hint(c.content_type_hint or "generic"),
                    document_type=c.document_type or "generic_page",
                    content_category=getattr(c, "content_category", None)
                    or detect_content_category(
                        url=c.url or "",
                        title=c.title or "",
                        heading=c.heading or "",
                        document_type=c.document_type or "generic_page",
                        content_type_hint=c.content_type_hint or "generic",
                        is_homepage=bool(c.is_homepage),
                    ),
                )
            )
        return hits


class HybridChunkRetriever:
    """Merge dense + lexical chunks without final document scoring."""

    def __init__(
        self,
        db: Session,
        settings: Settings,
        embedding: EmbeddingService,
        qdrant: QdrantService,
    ) -> None:
        self.settings = settings
        self.dense = EmbeddingRetriever(embedding, qdrant)
        self.lexical = LexicalRetriever(db)
        self.db = db

    def retrieve(
        self,
        *,
        normalized_query: str,
        top_k_dense: int,
        top_k_lexical: int,
        similarity_threshold: float,
        query_vector: list[float] | None = None,
        expansion_terms: list[str] | None = None,
        profile: KnowledgeProfile | None = None,
        query_intent: str = "unknown",
    ) -> tuple[list[SearchHit], ChunkRetrievalDebug]:
        s = self.settings
        profile = profile or KnowledgeProfileService.from_settings(s)
        mode = (s.retrieval_mode or "hybrid").lower()
        dbg = ChunkRetrievalDebug(normalized_query=normalized_query, mode=mode)

        dense_hits: list[SearchHit] = []
        if mode in ("dense", "hybrid"):
            dense_hits = self.dense.retrieve(
                normalized_query, top_k=top_k_dense, query_vector=query_vector
            )
        dbg.dense_count = len(dense_hits)

        lexical_hits: list[SearchHit] = []
        if mode in ("lexical", "hybrid") and self.lexical.enabled:
            lexical_hits, match_query, terms = self.lexical.retrieve(
                normalized_query,
                top_k=top_k_lexical,
                expansion_terms=expansion_terms,
                profile=profile,
                query_intent=query_intent,
                enable_expansion=s.enable_query_expansion,
            )
            dbg.match_query = match_query
            dbg.variants = terms[:20]
        dbg.lexical_count = len(lexical_hits)

        merged = self._merge(dense_hits, lexical_hits)
        self._attach_source_metadata(merged.values())
        kept = self._filter_grounding(merged, similarity_threshold)
        dbg.merged_count = len(kept)
        return kept, dbg

    def _merge(
        self, dense_hits: list[SearchHit], lexical_hits: list[SearchHit]
    ) -> dict[str, SearchHit]:
        merged: dict[str, SearchHit] = {}
        for hit in dense_hits:
            merged[_chunk_key(hit.source_id, hit.chunk_index)] = hit
        for hit in lexical_hits:
            key = _chunk_key(hit.source_id, hit.chunk_index)
            existing = merged.get(key)
            if existing is not None:
                existing.lexical_score = hit.lexical_score
            else:
                merged[key] = hit
        return merged

    def _attach_source_metadata(self, hits) -> None:
        ids = {h.source_id for h in hits}
        if not ids:
            return
        rows = self.db.execute(select(Source).where(Source.id.in_(ids))).scalars().all()
        meta = {
            s.id: {
                "boilerplate_ratio": float(s.boilerplate_ratio or 0.0),
                "document_type": s.document_type or "generic_page",
                "indexed_at": s.updated_at,
            }
            for s in rows
        }
        for hit in hits:
            m = meta.get(hit.source_id, {})
            hit.boilerplate_ratio = m.get("boilerplate_ratio", 0.0)
            if not hit.document_type or hit.document_type == "generic_page":
                hit.document_type = m.get("document_type", hit.document_type)

    @staticmethod
    def _filter_grounding(
        merged: dict[str, SearchHit], similarity_threshold: float
    ) -> list[SearchHit]:
        kept: list[SearchHit] = []
        for hit in merged.values():
            passes_dense = hit.dense_score >= similarity_threshold and hit.dense_score > 0
            is_lexical = hit.lexical_score > 0.0
            if not passes_dense and not is_lexical:
                hit.rejection_reason = "below_similarity_threshold"
                continue
            kept.append(hit)
        return kept
