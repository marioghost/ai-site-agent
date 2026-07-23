"""Pydantic schemas for Ollama model / status endpoints."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OllamaModel(BaseModel):
    name: str
    size: int | None = None
    modified_at: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    in_use_as: Literal["llm", "embedding"] | None = None


class ModelsResponse(BaseModel):
    models: list[OllamaModel]
    ollama_reachable: bool = True


class OllamaStatusResponse(BaseModel):
    status: str  # "ok" | "error"
    base_url: str
    detail: str | None = None
    models: list[str] = []


class OllamaModelActionRequest(BaseModel):
    model: str = Field(min_length=1, max_length=120)


class OllamaPullResponse(BaseModel):
    model: str
    status: str
    duration_ms: int = 0
    message: str = ""


class OllamaDeleteResponse(BaseModel):
    model: str
    status: str
    message: str = ""


class OllamaModelInstallStatus(BaseModel):
    model: str
    installed: bool
    in_use_as: Literal["llm", "embedding"] | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
