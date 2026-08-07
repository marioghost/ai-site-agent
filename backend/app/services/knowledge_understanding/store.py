"""Understanding Store — persistence for concept-index snapshots."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.knowledge_understanding import (
    UnderstandingConcept,
    UnderstandingEvidence,
    UnderstandingSnapshot,
)
from app.services.knowledge_understanding.builder import BuiltUnderstanding
from app.services.knowledge_understanding.embedding_codec import pack_embedding, unpack_embedding
from app.services.knowledge_understanding.models import Concept, EvidenceLink

REPRESENTATION = "concept_index"
KEEP_SNAPSHOTS = 3


class UnderstandingStore:
    """Versioned site-wide understanding persistence (concept index)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def latest_ready(self) -> UnderstandingSnapshot | None:
        return self.db.scalar(
            select(UnderstandingSnapshot)
            .where(UnderstandingSnapshot.status == "ready")
            .order_by(UnderstandingSnapshot.id.desc())
            .limit(1)
        )

    def latest(self) -> UnderstandingSnapshot | None:
        return self.db.scalar(
            select(UnderstandingSnapshot).order_by(UnderstandingSnapshot.id.desc()).limit(1)
        )

    def latest_error_after(self, snapshot_id: int | None) -> UnderstandingSnapshot | None:
        """Newest error snapshot newer than ``snapshot_id`` (if any)."""
        stmt = select(UnderstandingSnapshot).where(UnderstandingSnapshot.status == "error")
        if snapshot_id is not None:
            stmt = stmt.where(UnderstandingSnapshot.id > snapshot_id)
        return self.db.scalar(stmt.order_by(UnderstandingSnapshot.id.desc()).limit(1))

    def persist(
        self,
        built: BuiltUnderstanding,
        *,
        knowledge_version: int,
        build_duration_ms: int,
        status: str = "ready",
        error_message: str | None = None,
    ) -> UnderstandingSnapshot:
        now = datetime.now(timezone.utc)
        snapshot = UnderstandingSnapshot(
            knowledge_version=knowledge_version,
            concept_count=len(built.concepts),
            evidence_count=len(built.evidence),
            built_at=now,
            build_duration_ms=build_duration_ms,
            status=status,
            representation=REPRESENTATION,
            error_message=error_message,
        )
        self.db.add(snapshot)
        self.db.flush()

        for concept in built.concepts:
            self.db.add(
                UnderstandingConcept(
                    snapshot_id=snapshot.id,
                    concept_key=concept.concept_key,
                    label=concept.label,
                    aliases_json=json.dumps(concept.aliases, ensure_ascii=False),
                    embedding_blob=pack_embedding(concept.embedding),
                    confidence=float(concept.confidence),
                    evidence_count=len({m.source_id for m in concept.members if m.source_id}),
                    canonical_source_id=built.canonical_by_concept.get(concept.concept_key),
                )
            )

        for link in built.evidence:
            self.db.add(
                UnderstandingEvidence(
                    snapshot_id=snapshot.id,
                    concept_key=link.concept_key,
                    source_id=link.source_id,
                    relation=link.relation,
                    weight=float(link.weight),
                    confidence=float(link.confidence),
                )
            )

        self.db.flush()
        self._prune_old_snapshots(keep=KEEP_SNAPSHOTS)
        return snapshot

    def persist_error(
        self,
        *,
        knowledge_version: int,
        build_duration_ms: int,
        error_message: str,
    ) -> UnderstandingSnapshot:
        now = datetime.now(timezone.utc)
        snapshot = UnderstandingSnapshot(
            knowledge_version=knowledge_version,
            concept_count=0,
            evidence_count=0,
            built_at=now,
            build_duration_ms=build_duration_ms,
            status="error",
            representation=REPRESENTATION,
            error_message=(error_message or "")[:2000],
        )
        self.db.add(snapshot)
        self.db.flush()
        self._prune_old_snapshots(keep=KEEP_SNAPSHOTS)
        return snapshot

    def load_concepts(self, snapshot_id: int) -> list[Concept]:
        rows = self.db.scalars(
            select(UnderstandingConcept).where(UnderstandingConcept.snapshot_id == snapshot_id)
        ).all()
        out: list[Concept] = []
        for row in rows:
            try:
                aliases = json.loads(row.aliases_json or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                aliases = []
            if not isinstance(aliases, list):
                aliases = []
            out.append(
                Concept(
                    concept_key=row.concept_key,
                    label=row.label,
                    aliases=tuple(str(a) for a in aliases if a),
                    confidence=float(row.confidence or 0.0),
                    evidence_count=int(row.evidence_count or 0),
                    canonical_source_id=row.canonical_source_id,
                )
            )
        return out

    def load_embeddings(self, snapshot_id: int) -> dict[str, tuple[float, ...]]:
        """Adapter-internal concept embeddings — not part of the public Concept type."""
        rows = self.db.scalars(
            select(UnderstandingConcept).where(UnderstandingConcept.snapshot_id == snapshot_id)
        ).all()
        out: dict[str, tuple[float, ...]] = {}
        for row in rows:
            emb = unpack_embedding(row.embedding_blob)
            if emb is not None:
                out[row.concept_key] = emb
        return out

    def load_evidence(self, snapshot_id: int) -> list[EvidenceLink]:
        rows = self.db.scalars(
            select(UnderstandingEvidence).where(UnderstandingEvidence.snapshot_id == snapshot_id)
        ).all()
        return [
            EvidenceLink(
                concept_key=r.concept_key,
                source_id=int(r.source_id),
                relation=r.relation,
                weight=float(r.weight or 0.0),
                confidence=float(r.confidence or 0.0),
            )
            for r in rows
        ]

    def _prune_old_snapshots(self, *, keep: int) -> None:
        """Retain recent snapshots without ever dropping the latest ready snapshot.

        Error-only churn must not orphan the last good understanding model.
        """
        ids = list(
            self.db.scalars(
                select(UnderstandingSnapshot.id).order_by(UnderstandingSnapshot.id.desc())
            ).all()
        )
        if not ids:
            return
        keep_ids: set[int] = set(ids[:keep])
        ready = self.latest_ready()
        if ready is not None:
            keep_ids.add(int(ready.id))
        drop = [i for i in ids if i not in keep_ids]
        if not drop:
            return
        self.db.execute(
            delete(UnderstandingEvidence).where(UnderstandingEvidence.snapshot_id.in_(drop))
        )
        self.db.execute(
            delete(UnderstandingConcept).where(UnderstandingConcept.snapshot_id.in_(drop))
        )
        self.db.execute(delete(UnderstandingSnapshot).where(UnderstandingSnapshot.id.in_(drop)))
