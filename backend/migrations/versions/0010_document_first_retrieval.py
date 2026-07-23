"""Document-first retrieval engine settings."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_document_first_retrieval"
down_revision = "0009_cpu_local_model_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "retrieval_profile",
            sa.String(length=32),
            nullable=False,
            server_default="balanced",
        ),
    )
    op.add_column(
        "settings",
        sa.Column("document_priorities_json", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "settings",
        sa.Column("intent_profiles_json", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "settings",
        sa.Column("scoring_weights_json", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "settings",
        sa.Column("top_k_dense", sa.Integer(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("top_k_lexical", sa.Integer(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("rerank_limit", sa.Integer(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("document_limit", sa.Integer(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("minimum_retrieval_score", sa.Float(), nullable=True),
    )
    op.alter_column("settings", "retrieval_profile", server_default=None)


def downgrade() -> None:
    op.drop_column("settings", "minimum_retrieval_score")
    op.drop_column("settings", "document_limit")
    op.drop_column("settings", "rerank_limit")
    op.drop_column("settings", "top_k_lexical")
    op.drop_column("settings", "top_k_dense")
    op.drop_column("settings", "scoring_weights_json")
    op.drop_column("settings", "intent_profiles_json")
    op.drop_column("settings", "document_priorities_json")
    op.drop_column("settings", "retrieval_profile")
