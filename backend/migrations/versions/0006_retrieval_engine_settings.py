"""Retrieval engine settings — semantic expansion, context budget, streaming, retry."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_retrieval_engine_settings"
down_revision = "0005_sources_type_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("max_semantic_expansions", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column(
        "settings",
        sa.Column(
            "context_builder_mode",
            sa.String(length=32),
            nullable=False,
            server_default="full_content",
        ),
    )
    op.add_column(
        "settings",
        sa.Column("max_context_tokens", sa.Integer(), nullable=False, server_default="2048"),
    )
    op.add_column(
        "settings",
        sa.Column("chunk_merge_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "settings",
        sa.Column(
            "ranking_freshness_weight",
            sa.Float(),
            nullable=False,
            server_default="0.05",
        ),
    )
    op.add_column(
        "settings",
        sa.Column("enable_chat_streaming", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "settings",
        sa.Column("llm_retry_max_attempts", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "settings",
        sa.Column(
            "llm_retry_on_timeout_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    for col in (
        "max_semantic_expansions",
        "context_builder_mode",
        "max_context_tokens",
        "chunk_merge_enabled",
        "ranking_freshness_weight",
        "enable_chat_streaming",
        "llm_retry_max_attempts",
        "llm_retry_on_timeout_only",
    ):
        op.alter_column("settings", col, server_default=None)


def downgrade() -> None:
    op.drop_column("settings", "llm_retry_on_timeout_only")
    op.drop_column("settings", "llm_retry_max_attempts")
    op.drop_column("settings", "enable_chat_streaming")
    op.drop_column("settings", "ranking_freshness_weight")
    op.drop_column("settings", "chunk_merge_enabled")
    op.drop_column("settings", "max_context_tokens")
    op.drop_column("settings", "context_builder_mode")
    op.drop_column("settings", "max_semantic_expansions")
