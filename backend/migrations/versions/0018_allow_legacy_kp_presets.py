"""RFC-100 Step 054 — allow_legacy_kp_presets settings flag (default false)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_allow_legacy_kp_presets"
down_revision = "0017_memory_canonical_shadow_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "allow_legacy_kp_presets",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "allow_legacy_kp_presets")
