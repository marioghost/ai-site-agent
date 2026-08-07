"""Phase 0 — Knowledge Understanding Layer tables + feature flag."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_knowledge_understanding_phase0"
down_revision = "0020_step_063_kos_flags_default_on"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "enable_knowledge_understanding",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "understanding_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("knowledge_version", sa.Integer(), nullable=False),
        sa.Column("concept_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("build_duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column(
            "representation",
            sa.String(length=64),
            nullable=False,
            server_default="concept_index",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_understanding_snapshots_knowledge_version",
        "understanding_snapshots",
        ["knowledge_version"],
    )
    op.create_index(
        "ix_understanding_snapshots_status",
        "understanding_snapshots",
        ["status"],
    )

    op.create_table(
        "understanding_concepts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "snapshot_id",
            sa.Integer(),
            sa.ForeignKey("understanding_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("concept_key", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=256), nullable=False),
        sa.Column("aliases_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("embedding_blob", sa.LargeBinary(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("canonical_source_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id", "concept_key", name="uq_understanding_concepts_snapshot_key"
        ),
    )
    op.create_index(
        "ix_understanding_concepts_snapshot_id",
        "understanding_concepts",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_understanding_concepts_canonical_source_id",
        "understanding_concepts",
        ["canonical_source_id"],
    )

    op.create_table(
        "understanding_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "snapshot_id",
            sa.Integer(),
            sa.ForeignKey("understanding_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("concept_key", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("relation", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "concept_key",
            "source_id",
            "relation",
            name="uq_understanding_evidence_link",
        ),
    )
    op.create_index(
        "ix_understanding_evidence_snapshot_concept",
        "understanding_evidence",
        ["snapshot_id", "concept_key"],
    )
    op.create_index(
        "ix_understanding_evidence_source_id",
        "understanding_evidence",
        ["source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_understanding_evidence_source_id", table_name="understanding_evidence")
    op.drop_index(
        "ix_understanding_evidence_snapshot_concept", table_name="understanding_evidence"
    )
    op.drop_table("understanding_evidence")
    op.drop_index(
        "ix_understanding_concepts_canonical_source_id",
        table_name="understanding_concepts",
    )
    op.drop_index("ix_understanding_concepts_snapshot_id", table_name="understanding_concepts")
    op.drop_table("understanding_concepts")
    op.drop_index("ix_understanding_snapshots_status", table_name="understanding_snapshots")
    op.drop_index(
        "ix_understanding_snapshots_knowledge_version",
        table_name="understanding_snapshots",
    )
    op.drop_table("understanding_snapshots")
    op.drop_column("settings", "enable_knowledge_understanding")
