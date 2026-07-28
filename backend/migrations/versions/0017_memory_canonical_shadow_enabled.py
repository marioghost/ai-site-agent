"""RFC-100 Step 048 — memory_canonical_shadow_enabled settings flag."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_memory_canonical_shadow_enabled"
down_revision = "0016_memory_evidence_assist_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "memory_canonical_shadow_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "memory_canonical_shadow_enabled")
