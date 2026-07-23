"""Epistemic Memory ORM models (RFC-100 Step 027 — schema substrate only).

Tables are read via EpistemicMemoryService (Step 028). No production writes until Step 030+.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ObservationRef(Base):
    """Immutable reference to an informative observation event."""

    __tablename__ = "observation_ref"
    __table_args__ = (
        Index("ix_observation_ref_source_id", "source_id"),
        Index("ix_observation_ref_chunk_id", "chunk_id"),
        Index("ix_observation_ref_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    observation_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provenance_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    extraction_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    evidence_links: Mapped[list["EvidenceLink"]] = relationship(
        "EvidenceLink", back_populates="observation_ref"
    )


class EpistemicClaim(Base):
    """Attributed proposition — revisable via supersession/revision chain."""

    __tablename__ = "claim"
    __table_args__ = (
        Index("ix_claim_epistemic_status", "epistemic_status"),
        Index("ix_claim_attributed_to", "attributed_to"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposition: Mapped[str] = mapped_column(Text, nullable=False)
    scope_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    epistemic_status: Mapped[str] = mapped_column(String(32), default="provisional")
    attributed_to: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    superseded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("claim.id", ondelete="SET NULL"), nullable=True
    )
    revision_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("claim.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    evidence_links: Mapped[list["EvidenceLink"]] = relationship(
        "EvidenceLink", back_populates="claim", cascade="all, delete-orphan"
    )
    superseded_by: Mapped["EpistemicClaim | None"] = relationship(
        "EpistemicClaim",
        remote_side="EpistemicClaim.id",
        foreign_keys=[superseded_by_id],
    )
    revision_of: Mapped["EpistemicClaim | None"] = relationship(
        "EpistemicClaim",
        remote_side="EpistemicClaim.id",
        foreign_keys=[revision_of_id],
    )


class EvidenceLink(Base):
    """Connects a claim to an immutable observation with a provenance role."""

    __tablename__ = "evidence_link"
    __table_args__ = (
        Index("ix_evidence_link_claim_id", "claim_id"),
        Index("ix_evidence_link_observation_ref_id", "observation_ref_id"),
        Index("ix_evidence_link_role", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claim.id", ondelete="CASCADE"), nullable=False
    )
    observation_ref_id: Mapped[int] = mapped_column(
        ForeignKey("observation_ref.id", ondelete="RESTRICT"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    provenance_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    link_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    claim: Mapped["EpistemicClaim"] = relationship(
        "EpistemicClaim", back_populates="evidence_links"
    )
    observation_ref: Mapped["ObservationRef"] = relationship(
        "ObservationRef", back_populates="evidence_links"
    )
