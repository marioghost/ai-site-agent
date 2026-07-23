"""Shared Pydantic schemas."""
from __future__ import annotations

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class HealthComponent(BaseModel):
    """Status of a single subsystem."""

    status: str  # "ok" | "error" | "unknown"
    detail: str | None = None


class DatabaseHealth(HealthComponent):
    """PostgreSQL health detail."""

    engine: str = "PostgreSQL"
    migration_version: str | None = None
    latency_ms: float | None = None
    pool: str | None = None
    pool_checked_out: int | None = None
    pool_size: int | None = None
    pool_overflow: int | None = None
    slow_queries: list[dict] | None = None


class HealthResponse(BaseModel):
    app: HealthComponent
    ollama: HealthComponent
    qdrant: HealthComponent
    database: DatabaseHealth


class ChatSource(BaseModel):
    title: str
    url: str
    source_type: str
    score: float
