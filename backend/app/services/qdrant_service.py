"""Qdrant vector store service.

Uses the qdrant-client REST interface against a locally-installed Qdrant
(non-Docker binary). Handles collection creation, upsert, delete-by-source and
similarity search.
"""
from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SearchHit:
    score: float
    source_id: int
    chunk_index: int
    title: str
    url: str
    source_type: str
    text: str
    heading: str = ""
    is_homepage: bool = False
    is_structured_block: bool = False
    content_type_hint: str = "generic"
    document_type: str = "generic_page"
    content_category: str = "generic"
    # Populated by hybrid retrieval for debugging / fusion.
    dense_score: float = 0.0
    lexical_score: float = 0.0
    final_score: float = 0.0
    title_score: float = 0.0
    main_content_score: float = 0.0
    boilerplate_score: float = 0.0
    url_score: float = 0.0
    metadata_boost: float = 0.0
    intent_boost: float = 0.0
    boilerplate_ratio: float = 0.0
    selection_reason: str = ""
    rejection_reason: str = ""
    score_breakdown: dict | None = None
    # Source Intelligence (debug / routing)
    page_role: str = ""
    importance: int = 0
    content_quality: int = 0
    source_canonical: bool = False
    source_profile_summary: str = ""
    profile_routing_reason: str = ""
    source_language: str = "unknown"
    # SI document purpose (evidence/authority vocabulary).
    document_purpose: str = ""
    # Content fingerprint for cross-URL duplicate evidence control.
    content_hash: str = ""
    # Populated by canonical source selection.
    is_canonical: bool = False
    excluded_as_news: bool = False


class QdrantService:
    def __init__(
        self,
        collection: str,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        config = get_config()
        self.collection = collection
        self.client = QdrantClient(
            host=host or config.qdrant_host,
            port=port or config.qdrant_port,
            timeout=30.0,
        )

    def health(self) -> tuple[bool, str]:
        try:
            self.client.get_collections()
            return True, "Qdrant reachable"
        except Exception as exc:  # noqa: BLE001
            return False, f"Qdrant unreachable: {exc}"

    def ensure_collection(
        self, vector_size: int, with_source_index: bool = True
    ) -> None:
        """Create the collection if it does not exist."""
        try:
            existing = {c.name for c in self.client.get_collections().collections}
            if self.collection in existing:
                return
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(
                    size=vector_size, distance=qmodels.Distance.COSINE
                ),
            )
            if with_source_index:
                # Index on source_id so we can delete a source's points efficiently.
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name="source_id",
                    field_schema=qmodels.PayloadSchemaType.INTEGER,
                )
            logger.info("Created Qdrant collection '%s'", self.collection)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed ensuring Qdrant collection: %s", exc)
            raise

    def search_ids(self, vector: list[float], top_k: int) -> list[tuple[str, float]]:
        """Return (point_id, score) for the top_k nearest points.

        Used by the semantic answer cache where the point id maps back to a
        SQLite metadata row.
        """
        try:
            results = self.client.query_points(
                collection_name=self.collection,
                query=vector,
                limit=top_k,
                with_payload=False,
            ).points
        except Exception as exc:  # noqa: BLE001
            logger.warning("Answer-cache search failed: %s", exc)
            return []
        return [(str(r.id), float(r.score)) for r in results]

    def delete_points(self, point_ids: list[str]) -> None:
        """Delete specific points by id."""
        if not point_ids:
            return
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=qmodels.PointIdsList(points=point_ids),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed deleting points: %s", exc)

    def delete_collection(self) -> None:
        """Drop the whole collection (used by reindex-all). Safe if missing."""
        try:
            self.client.delete_collection(collection_name=self.collection)
            logger.info("Deleted Qdrant collection '%s'", self.collection)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed deleting Qdrant collection: %s", exc)

    def delete_source_points(self, source_id: int) -> None:
        """Delete all points belonging to a given source."""
        self.client.delete(
            collection_name=self.collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="source_id",
                            match=qmodels.MatchValue(value=source_id),
                        )
                    ]
                )
            ),
        )

    def upsert_chunks(
        self,
        point_ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        """Upsert a batch of chunk vectors with payloads."""
        points = [
            qmodels.PointStruct(id=pid, vector=vec, payload=payload)
            for pid, vec, payload in zip(point_ids, vectors, payloads)
        ]
        if not points:
            return
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, vector: list[float], top_k: int) -> list[SearchHit]:
        """Return the top_k most similar chunks."""
        results = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=top_k,
            with_payload=True,
        ).points
        hits: list[SearchHit] = []
        for r in results:
            payload = r.payload or {}
            score = float(r.score)
            hits.append(
                SearchHit(
                    score=score,
                    source_id=int(payload.get("source_id", 0)),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    title=payload.get("title", "") or "",
                    url=payload.get("url", "") or "",
                    source_type=payload.get("source_type", "") or "",
                    text=payload.get("text", "") or "",
                    heading=payload.get("heading", "") or "",
                    is_homepage=bool(payload.get("is_homepage", False)),
                    is_structured_block=bool(payload.get("is_structured_block", False)),
                    content_type_hint=payload.get("content_type_hint", "generic")
                    or "generic",
                    document_type=payload.get("document_type", "generic_page")
                    or "generic_page",
                    content_category=payload.get("content_category", "generic") or "generic",
                    dense_score=score,
                )
            )
        return hits

    def count(self) -> int:
        try:
            return self.client.count(collection_name=self.collection).count
        except Exception:  # noqa: BLE001
            return 0
