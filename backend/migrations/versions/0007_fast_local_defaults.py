"""Fast local defaults: polish off, fast profile, streaming on."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_fast_local_defaults"
down_revision = "0006_retrieval_engine_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE settings SET polish_mode = 'off', llm_mode_profile = 'fast', "
            "enable_chat_streaming = true "
            "WHERE id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE settings SET llm_mode_profile = 'balanced' WHERE id IS NOT NULL"
        )
    )
