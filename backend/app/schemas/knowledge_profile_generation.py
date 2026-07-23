"""Schemas for AI Knowledge Profile generation wizard."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.knowledge_profile import KnowledgeProfile

GenerationSection = Literal[
    "organization",
    "topics",
    "aliases",
    "query_patterns",
    "document_types",
    "retrieval_rules",
    "query_expansions",
    "everything",
]


class ConfidenceItem(BaseModel):
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    detail: str = ""
    page_count: int = 0
    evidence: list[str] = Field(default_factory=list)


class WebsiteStructureSummary(BaseModel):
    indexed_page_count: int = 0
    indexed_file_count: int = 0
    total_chunks: int = 0
    site_url: str = ""
    top_url_segments: list[str] = Field(default_factory=list)
    sample_titles: list[str] = Field(default_factory=list)
    sample_headings: list[str] = Field(default_factory=list)
    document_type_counts: dict[str, int] = Field(default_factory=dict)
    content_hint_counts: dict[str, int] = Field(default_factory=dict)
    homepage_excerpt: str = ""


class GenerationPreview(BaseModel):
    organization: ConfidenceItem | None = None
    website_type: ConfidenceItem | None = None
    website_type_secondary: ConfidenceItem | None = None
    topics: list[ConfidenceItem] = Field(default_factory=list)
    aliases: list[ConfidenceItem] = Field(default_factory=list)
    document_types: list[ConfidenceItem] = Field(default_factory=list)
    overview_patterns: list[ConfidenceItem] = Field(default_factory=list)
    profile: KnowledgeProfile | None = None
    website_structure: WebsiteStructureSummary | None = None
    preset_seed: str = ""
    low_confidence_keys: list[str] = Field(default_factory=list)
    entities: list[ConfidenceItem] = Field(default_factory=list)
    content_hints: list[ConfidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation_issues: list[dict[str, object]] = Field(default_factory=list)
    analytics: dict[str, object] = Field(default_factory=dict)


class ProfileGenerationJobStatus(BaseModel):
    id: int
    status: str
    current_stage: str = ""
    progress_percent: int = 0
    started_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    preview: GenerationPreview | None = None
    log_tail: list[dict[str, str]] = Field(default_factory=list)
    analytics: dict[str, Any] = Field(default_factory=dict)


class GenerateProfileRequest(BaseModel):
    sections: list[GenerationSection] = Field(default_factory=lambda: ["everything"])
    merge_identity: bool = False
    use_llm: bool = True


class ApplyGeneratedProfileRequest(BaseModel):
    profile: KnowledgeProfile
    sections: list[GenerationSection] = Field(default_factory=lambda: ["everything"])
