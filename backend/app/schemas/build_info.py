"""Build / release metadata schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DeployedCapability(BaseModel):
    """Whether this running process supports a migration flag and its value."""

    supported: bool
    value: bool | None = None
    surface: str = Field(description="env | settings | unknown")
    friendly_name: str = ""
    default: bool = False
    effect: str = ""
    rollout: str = ""


class ReleaseStatus(BaseModel):
    accepted: str
    in_progress: str | None = None
    closed_0_6: bool = False
    note: str = ""


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
    release_status: ReleaseStatus | None = None
    deployed_capabilities: dict[str, DeployedCapability] = Field(default_factory=dict)
