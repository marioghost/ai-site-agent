"""Add max_concurrent_background_embedding_requests to settings.

Revision ID: 0004_bg_embed_limit
Revises: 0003_performance
Create Date: 2026-06-30

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_bg_embed_limit"
down_revision: Union[str, None] = "0003_performance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "max_concurrent_background_embedding_requests",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    # Drop the server default so the ORM default governs new rows going forward.
    op.alter_column(
        "settings",
        "max_concurrent_background_embedding_requests",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("settings", "max_concurrent_background_embedding_requests")
