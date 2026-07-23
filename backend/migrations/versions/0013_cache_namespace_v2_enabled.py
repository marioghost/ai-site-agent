"""RFC-100 Step 023 — cache_namespace_v2_enabled settings flag."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_cache_namespace_v2_enabled"
down_revision = "0012_memory_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "cache_namespace_v2_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "cache_namespace_v2_enabled")
