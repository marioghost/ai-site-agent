"""RFC-100 Step 063 — default Knowledge OS settings flags ON (Release 1.0).

Does not change legacy flags:
- allow_legacy_kp_presets (remains false)
- legacy_doc_type_canonical_enabled (remains false)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_step_063_kos_flags_default_on"
down_revision = "0019_legacy_doc_type_canonical_enabled"
branch_labels = None
depends_on = None

_FLAG_COLUMNS = (
    "enable_semantic_diagnostics_v2",
    "cache_namespace_v2_enabled",
    "memory_shadow_write_enabled",
    "memory_evidence_assist_enabled",
    "memory_canonical_shadow_enabled",
)


def upgrade() -> None:
    for col in _FLAG_COLUMNS:
        op.execute(
            sa.text(f"UPDATE settings SET {col} = true WHERE {col} IS DISTINCT FROM true")
        )
        op.alter_column(
            "settings",
            col,
            existing_type=sa.Boolean(),
            server_default=sa.true(),
            existing_nullable=False,
        )


def downgrade() -> None:
    for col in _FLAG_COLUMNS:
        op.alter_column(
            "settings",
            col,
            existing_type=sa.Boolean(),
            server_default=sa.false(),
            existing_nullable=False,
        )
