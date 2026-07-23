"""Add composite index on sources (source_type, status).

Revision ID: 0005_sources_type_status
Revises: 0004_bg_embed_limit
Create Date: 2026-06-30

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005_sources_type_status"
down_revision: Union[str, None] = "0004_bg_embed_limit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_sources_source_type_status",
        "sources",
        ["source_type", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sources_source_type_status", table_name="sources")
