"""RFC-100 Step 014 — enable_semantic_diagnostics_v2 settings flag."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_semantic_diagnostics_v2"
down_revision = "0010_document_first_retrieval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "enable_semantic_diagnostics_v2",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "enable_semantic_diagnostics_v2")
