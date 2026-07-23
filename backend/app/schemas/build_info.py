"""Build / release metadata schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class BuildInfoResponse(BaseModel):
    """Deploy artifact identity and active RFC-100 flags."""

    app_version: str
    release: str
    git_commit: str | None = None
    git_commit_short: str | None = None
    build_time: str | None = None
    alembic_head: str | None = None
    memory_version: int
    knowledge_version: int
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    env_flags: dict[str, bool] = Field(default_factory=dict)
    settings_flags: dict[str, bool] = Field(default_factory=dict)
