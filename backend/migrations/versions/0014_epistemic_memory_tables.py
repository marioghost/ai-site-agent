"""RFC-100 Step 027 — Epistemic Memory tables (schema only, inactive at runtime)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_epistemic_memory_tables"
down_revision = "0013_cache_namespace_v2_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observation_ref",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("observation_key", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provenance_kind", sa.String(length=64), nullable=False),
        sa.Column("provenance_ref", sa.String(length=256), nullable=True),
        sa.Column("extraction_version", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_key", name="uq_observation_ref_observation_key"),
    )
    op.create_index("ix_observation_ref_source_id", "observation_ref", ["source_id"])
    op.create_index("ix_observation_ref_chunk_id", "observation_ref", ["chunk_id"])
    op.create_index("ix_observation_ref_content_hash", "observation_ref", ["content_hash"])

    op.create_table(
        "claim",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("proposition", sa.Text(), nullable=False),
        sa.Column("scope_json", sa.Text(), nullable=True),
        sa.Column(
            "epistemic_status",
            sa.String(length=32),
            nullable=False,
            server_default="provisional",
        ),
        sa.Column("attributed_to", sa.String(length=64), nullable=False),
        sa.Column("provenance_kind", sa.String(length=64), nullable=False),
        sa.Column("provenance_ref", sa.String(length=256), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "superseded_by_id",
            sa.Integer(),
            sa.ForeignKey("claim.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "revision_of_id",
            sa.Integer(),
            sa.ForeignKey("claim.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claim_epistemic_status", "claim", ["epistemic_status"])
    op.create_index("ix_claim_attributed_to", "claim", ["attributed_to"])
    op.create_index("ix_claim_superseded_by_id", "claim", ["superseded_by_id"])
    op.create_index("ix_claim_revision_of_id", "claim", ["revision_of_id"])

    op.create_table(
        "evidence_link",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "claim_id",
            sa.Integer(),
            sa.ForeignKey("claim.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "observation_ref_id",
            sa.Integer(),
            sa.ForeignKey("observation_ref.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("provenance_kind", sa.String(length=64), nullable=False),
        sa.Column("provenance_ref", sa.String(length=256), nullable=True),
        sa.Column("link_confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_link_claim_id", "evidence_link", ["claim_id"])
    op.create_index(
        "ix_evidence_link_observation_ref_id", "evidence_link", ["observation_ref_id"]
    )
    op.create_index("ix_evidence_link_role", "evidence_link", ["role"])


def downgrade() -> None:
    op.drop_index("ix_evidence_link_role", table_name="evidence_link")
    op.drop_index("ix_evidence_link_observation_ref_id", table_name="evidence_link")
    op.drop_index("ix_evidence_link_claim_id", table_name="evidence_link")
    op.drop_table("evidence_link")

    op.drop_index("ix_claim_revision_of_id", table_name="claim")
    op.drop_index("ix_claim_superseded_by_id", table_name="claim")
    op.drop_index("ix_claim_attributed_to", table_name="claim")
    op.drop_index("ix_claim_epistemic_status", table_name="claim")
    op.drop_table("claim")

    op.drop_index("ix_observation_ref_content_hash", table_name="observation_ref")
    op.drop_index("ix_observation_ref_chunk_id", table_name="observation_ref")
    op.drop_index("ix_observation_ref_source_id", table_name="observation_ref")
    op.drop_table("observation_ref")
