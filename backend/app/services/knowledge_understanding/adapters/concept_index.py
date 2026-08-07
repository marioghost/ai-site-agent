"""Concept Index adapter — MVP KnowledgeUnderstandingLayer implementation."""
from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.source import Source
from app.services.knowledge_understanding.diagnostics import (
    build_understanding_trace,
    explain_match_for_source,
)
from app.services.knowledge_understanding.evidence_finder import EvidenceFinder
from app.services.knowledge_understanding.models import (
    Concept,
    CoverageGap,
    EvidenceLink,
    QueryNeedInput,
    ResolvedNeed,
    UnderstandingMatch,
    UnderstandingSummary,
)
from app.services.knowledge_understanding.resolver import UnderstandingResolver
from app.services.knowledge_understanding.similarity import cosine
from app.services.knowledge_understanding.store import UnderstandingStore

WEAK_EVIDENCE = 1
WEAK_CONFIDENCE = 0.45
RELATED_MIN_SIM = 0.55


class ConceptIndexUnderstandingLayer:
    """Site-wide understanding backed by concept index + embedding merge."""

    def __init__(
        self,
        db: Session,
        *,
        enabled: bool = True,
        source_meta: Mapping[int, tuple[str, str]] | None = None,
    ) -> None:
        self.db = db
        self.enabled = enabled
        self._store = UnderstandingStore(db)
        self._resolver = UnderstandingResolver()
        self._finder = EvidenceFinder()
        self._source_meta = dict(source_meta or {})
        self._concepts: list[Concept] | None = None
        self._embeddings: dict[str, tuple[float, ...]] | None = None
        self._evidence: list[EvidenceLink] | None = None
        self._snapshot_id: int | None = None

    def _ensure_loaded(self) -> bool:
        if self._concepts is not None:
            return True
        snap = self._store.latest_ready()
        if snap is None:
            self._concepts = []
            self._embeddings = {}
            self._evidence = []
            self._snapshot_id = None
            return False
        self._snapshot_id = snap.id
        self._concepts = self._store.load_concepts(snap.id)
        self._embeddings = self._store.load_embeddings(snap.id)
        self._evidence = self._store.load_evidence(snap.id)
        if not self._source_meta:
            self._source_meta = self._load_source_meta()
        return True

    def _load_source_meta(self) -> dict[int, tuple[str, str]]:
        ids: set[int] = set()
        for link in self._evidence or []:
            ids.add(link.source_id)
        for concept in self._concepts or []:
            if concept.canonical_source_id is not None:
                ids.add(concept.canonical_source_id)
        if not ids:
            return {}
        rows = self.db.scalars(select(Source).where(Source.id.in_(ids))).all()
        return {int(s.id): (s.url or "", s.title or "") for s in rows}

    def resolve_query(
        self,
        understanding: QueryNeedInput,
        *,
        query_embedding: list[float] | None = None,
    ) -> ResolvedNeed:
        self._ensure_loaded()
        return self._resolver.resolve(
            understanding,
            self._concepts or [],
            query_embedding=query_embedding,
            concept_embeddings=self._embeddings or {},
        )

    def find_evidence(
        self,
        need: ResolvedNeed,
        *,
        limit: int = 24,
    ) -> list[UnderstandingMatch]:
        self._ensure_loaded()
        return self._finder.find(
            need,
            evidence=self._evidence or [],
            concepts=self._concepts or [],
            source_meta=self._source_meta,
            limit=limit,
        )

    def canonical_for(self, concept_key: str) -> int | None:
        self._ensure_loaded()
        for concept in self._concepts or []:
            if concept.concept_key == concept_key:
                return concept.canonical_source_id
        return None

    def related_knowledge(
        self,
        concept_key: str,
        *,
        limit: int = 8,
    ) -> list[Concept]:
        self._ensure_loaded()
        concepts = self._concepts or []
        embeddings = self._embeddings or {}
        target_emb = embeddings.get(concept_key)
        if target_emb is None:
            return []
        scored: list[tuple[float, Concept]] = []
        for concept in concepts:
            if concept.concept_key == concept_key:
                continue
            emb = embeddings.get(concept.concept_key)
            if not emb:
                continue
            scored.append((cosine(target_emb, emb), concept))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [c for score, c in scored[:limit] if score >= RELATED_MIN_SIM]

    def coverage_gaps(self, *, limit: int = 40) -> list[CoverageGap]:
        self._ensure_loaded()
        gaps: list[CoverageGap] = []
        for concept in self._concepts or []:
            if concept.evidence_count <= WEAK_EVIDENCE:
                gaps.append(
                    CoverageGap(
                        concept_key=concept.concept_key,
                        label=concept.label,
                        reason="Weak evidence coverage — few sources explain this concept.",
                        evidence_count=concept.evidence_count,
                        confidence=concept.confidence,
                    )
                )
            elif concept.confidence < WEAK_CONFIDENCE:
                gaps.append(
                    CoverageGap(
                        concept_key=concept.concept_key,
                        label=concept.label,
                        reason="Low confidence concept extracted from Source Intelligence.",
                        evidence_count=concept.evidence_count,
                        confidence=concept.confidence,
                    )
                )
        gaps.sort(key=lambda g: (g.evidence_count, g.confidence))
        return gaps[:limit]

    def explain_match(
        self,
        source_id: int,
        need: ResolvedNeed,
    ) -> str:
        matches = self.find_evidence(need, limit=50)
        return explain_match_for_source(source_id, need, matches)

    def list_concepts(self, *, limit: int = 100) -> list[Concept]:
        self._ensure_loaded()
        concepts = list(self._concepts or [])
        concepts.sort(key=lambda c: (c.evidence_count, c.confidence), reverse=True)
        return concepts[:limit]

    def sources_for_concept(self, concept_key: str) -> list[UnderstandingMatch]:
        concept = self.concept_by_key(concept_key)
        if concept is None:
            return []
        need = ResolvedNeed(
            concepts=(concept,),
            need_type="general",
            query_terms=(),
            resolution_method="direct",
        )
        return self.find_evidence(need, limit=50)

    def concept_by_key(self, concept_key: str) -> Concept | None:
        self._ensure_loaded()
        return next(
            (c for c in (self._concepts or []) if c.concept_key == concept_key),
            None,
        )

    def summary(self) -> UnderstandingSummary:
        ready = self._store.latest_ready()
        latest = self._store.latest()
        if ready is None and latest is None:
            return UnderstandingSummary(
                enabled=self.enabled,
                knowledge_version=None,
                snapshot_id=None,
                status="missing",
                representation="concept_index",
                concept_count=0,
                evidence_count=0,
                built_at=None,
                build_duration_ms=0,
                error_message=None,
            )

        # Active payload always from latest ready; errors are advisory side-channel.
        snap = ready or latest
        assert snap is not None
        self._ensure_loaded()
        top = [
            {
                "concept_key": c.concept_key,
                "label": c.label,
                "evidence_count": c.evidence_count,
                "confidence": round(c.confidence, 3),
                "canonical_source_id": c.canonical_source_id,
            }
            for c in self.list_concepts(limit=20)
        ]
        gaps = [
            {
                "concept_key": g.concept_key,
                "label": g.label,
                "reason": g.reason,
                "evidence_count": g.evidence_count,
            }
            for g in self.coverage_gaps(limit=20)
        ]
        built_at = snap.built_at.isoformat() if snap.built_at else None
        err = self._store.latest_error_after(ready.id if ready else None)
        return UnderstandingSummary(
            enabled=self.enabled,
            knowledge_version=snap.knowledge_version,
            snapshot_id=snap.id,
            status=snap.status if ready is not None else snap.status,
            representation=snap.representation,
            concept_count=snap.concept_count if ready is not None else 0,
            evidence_count=snap.evidence_count if ready is not None else 0,
            built_at=built_at if ready is not None else None,
            build_duration_ms=snap.build_duration_ms if ready is not None else 0,
            top_concepts=top if ready is not None else [],
            coverage_gaps=gaps if ready is not None else [],
            error_message=snap.error_message if ready is None else None,
            last_error_message=err.error_message if err is not None else None,
            last_error_at=err.built_at.isoformat() if err is not None and err.built_at else None,
        )

    def understanding_trace(
        self,
        understanding: QueryNeedInput,
        *,
        query_embedding: list[float] | None = None,
        selected_limit: int = 3,
    ) -> dict:
        if not self.enabled:
            return build_understanding_trace(enabled=False, need=None, matches=[])
        need = self.resolve_query(understanding, query_embedding=query_embedding)
        matches = self.find_evidence(need)
        return build_understanding_trace(
            enabled=True,
            need=need,
            matches=matches,
            selected_limit=selected_limit,
        )
