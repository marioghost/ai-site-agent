"""RFC-100 Step 030 — memory_shadow_write_enabled settings flag."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_memory_shadow_write_enabled"
down_revision = "0014_epistemic_memory_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "memory_shadow_write_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "memory_shadow_write_enabled")
