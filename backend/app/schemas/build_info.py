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
    active: bool | None = None
    code_present: bool | None = None
    effective: bool | None = None
    skipped_reason: str | None = None


class ReleaseCapabilityState(BaseModel):
    """Repository capability vs runtime enablement (not the same as deployed)."""

    code_present: bool = True
    configured: bool | None = None
    enabled: bool | None = None
    effective: bool | None = None
    note: str | None = None


class ReleaseStatus(BaseModel):
    accepted: str
    in_progress: str | None = None
    closed_0_6: bool = False
    closed_0_7: bool = False
    closed_0_8: bool = False
    closed_0_9: bool = False
    engineering_ready: bool = False
    staging_validated: bool = False
    production_ready: bool = False
    steps_039_045: list[dict[str, Any]] = Field(default_factory=list)
    steps_046_050: list[dict[str, Any]] = Field(default_factory=list)
    steps_046_048: list[dict[str, Any]] = Field(default_factory=list)
    steps_052_057: list[dict[str, Any]] = Field(default_factory=list)
    steps_058_062: list[dict[str, Any]] = Field(default_factory=list)
    steps_063: list[dict[str, Any]] = Field(default_factory=list)
    release_0_7_capabilities: dict[str, ReleaseCapabilityState] = Field(
        default_factory=dict
    )
    release_0_8_capabilities: dict[str, ReleaseCapabilityState] = Field(
        default_factory=dict
    )
    release_0_9_capabilities: dict[str, ReleaseCapabilityState] = Field(
        default_factory=dict
    )
    note: str = ""


class BuildInfoResponse(BaseModel):
    """Deploy artifact identity and active RFC-100 flags."""

    app_version: str
    release: str
    git_commit: str | None = None
    git_commit_short: str | None = None
    backend_commit: str | None = None
    frontend_commit: str | None = None
    source_ref: str | None = None
    build_time: str | None = None
    alembic_head: str | None = None
    memory_version: int
    knowledge_version: int
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    env_flags: dict[str, bool] = Field(default_factory=dict)
    settings_flags: dict[str, bool] = Field(default_factory=dict)
    release_status: ReleaseStatus | None = None
    deployed_capabilities: dict[str, DeployedCapability] = Field(default_factory=dict)
