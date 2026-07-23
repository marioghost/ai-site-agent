"""Performance indexes, job events, and analytics aggregates.

Revision ID: 0003_performance
Revises: 0002_widen_cache_type
Create Date: 2026-06-30

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_performance"
down_revision: Union[str, None] = "0002_widen_cache_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["index_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])
    op.create_index(
        "ix_job_events_job_id_created_at", "job_events", ["job_id", "created_at"]
    )

    op.create_table(
        "analytics_hourly",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hour_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("avg_latency_ms", sa.Float(), nullable=False),
        sa.Column("cache_hit_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("fallback_count", sa.Integer(), nullable=False),
        sa.Column("intent_informational", sa.Integer(), nullable=False),
        sa.Column("intent_navigational", sa.Integer(), nullable=False),
        sa.Column("intent_transactional", sa.Integer(), nullable=False),
        sa.Column("intent_other", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analytics_hourly_hour_start", "analytics_hourly", ["hour_start"], unique=True
    )

    op.create_index(
        "ix_sources_needs_intelligence_true",
        "sources",
        ["id"],
        postgresql_where=sa.text("needs_intelligence IS TRUE"),
    )
    op.create_index(
        "ix_sources_needs_reprocess_true",
        "sources",
        ["id"],
        postgresql_where=sa.text("needs_reprocess IS TRUE"),
    )
    op.create_index(
        "ix_index_jobs_status_updated_at", "index_jobs", ["status", "updated_at"]
    )
    op.create_index(
        "ix_index_jobs_running",
        "index_jobs",
        ["updated_at"],
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "ix_chunks_source_id",
        "chunks",
        ["source_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_chat_logs_created_at",
        "chat_logs",
        ["created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_logs_created_at", table_name="chat_logs")
    op.drop_index("ix_chunks_source_id", table_name="chunks")
    op.drop_index("ix_index_jobs_running", table_name="index_jobs")
    op.drop_index("ix_index_jobs_status_updated_at", table_name="index_jobs")
    op.drop_index("ix_sources_needs_reprocess_true", table_name="sources")
    op.drop_index("ix_sources_needs_intelligence_true", table_name="sources")
    op.drop_index("ix_analytics_hourly_hour_start", table_name="analytics_hourly")
    op.drop_table("analytics_hourly")
    op.drop_index("ix_job_events_job_id_created_at", table_name="job_events")
    op.drop_index("ix_job_events_job_id", table_name="job_events")
    op.drop_table("job_events")
