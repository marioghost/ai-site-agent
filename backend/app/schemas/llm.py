"""Pydantic schemas for LLM benchmark/runtime endpoints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LlmBenchmarkScenario(BaseModel):
    key: str
    error: str | None = None
    answer_preview: str = ""
    total_duration_ms: int = 0
    load_duration_ms: int | None = None
    prompt_eval_duration_ms: int | None = None
    eval_duration_ms: int | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None
    tokens_per_second: float = 0.0
    time_to_first_token_ms: int | None = None
    connection_ms: int | None = None
    model: str = ""
    options: dict[str, Any] = Field(default_factory=dict)


class LlmBenchmarkResponse(BaseModel):
    model: str
    options: dict[str, Any] = Field(default_factory=dict)
    model_warm: bool = False
    warmup_status: str = "cold"
    environment: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[LlmBenchmarkScenario] = Field(default_factory=list)


class LlmRuntimeInfoResponse(BaseModel):
    ollama_reachable: bool
    ollama_detail: str | None = None
    ollama_version: str | None = None
    active_model: str
    model_installed: bool = True
    installed_models: list[str] = Field(default_factory=list)
    warmup: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    recommended_models: list[dict[str, str]] = Field(default_factory=list)
