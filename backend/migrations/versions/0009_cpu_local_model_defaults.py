"""CPU-friendly defaults: qwen2.5:3b chat model, fast profile, polish off."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_cpu_local_model_defaults"
down_revision = "0008_chat_message_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE settings SET "
            "llm_model = 'qwen2.5:3b', "
            "llm_mode_profile = 'fast', "
            "polish_mode = 'off', "
            "fast_mode_enabled = false, "
            "llm_keep_alive = '30m', "
            "enable_llm_warmup = true, "
            "enable_chat_streaming = true, "
            "ollama_generation_timeout_seconds = 45 "
            "WHERE id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE settings SET llm_model = 'qwen2.5:7b', llm_mode_profile = 'fast' "
            "WHERE id IS NOT NULL"
        )
    )
