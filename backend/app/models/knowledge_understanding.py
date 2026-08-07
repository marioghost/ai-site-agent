"""ORM models for Knowledge Understanding Layer (Phase 0 concept index)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UnderstandingSnapshot(Base):
    __tablename__ = "understanding_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    concept_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    build_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready", index=True)
    representation: Mapped[str] = mapped_column(
        String(64), nullable=False, default="concept_index"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class UnderstandingConcept(Base):
    __tablename__ = "understanding_concepts"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "concept_key", name="uq_understanding_concepts_snapshot_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("understanding_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_key: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    aliases_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    embedding_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    canonical_source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class UnderstandingEvidence(Base):
    __tablename__ = "understanding_evidence"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "concept_key",
            "source_id",
            "relation",
            name="uq_understanding_evidence_link",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("understanding_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    concept_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    relation: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
