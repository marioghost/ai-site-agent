"""RFC-100 Step 020 — memory_version on settings (epistemic memory substrate)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_memory_version"
down_revision = "0011_semantic_diagnostics_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "memory_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "memory_version")
