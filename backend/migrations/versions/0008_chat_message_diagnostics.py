"""Persist per-message diagnostics for chat session history."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_chat_message_diagnostics"
down_revision = "0007_fast_local_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("diagnostics_json", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "diagnostics_json")
