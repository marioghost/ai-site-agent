"""RFC-100 Step 055 — legacy_doc_type_canonical_enabled settings flag (default false)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_legacy_doc_type_canonical_enabled"
down_revision = "0018_allow_legacy_kp_presets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "legacy_doc_type_canonical_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "legacy_doc_type_canonical_enabled")
