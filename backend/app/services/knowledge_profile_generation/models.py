"""Data models for the Knowledge Profile generation pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.knowledge_profile import (
    ContentHintRule,
    DocumentTypeRule,
    ImportantTopic,
    KnowledgeProfile,
    QueryExpansionRule,
    SourcePriorityRule,
)


class EvidenceItem(BaseModel):
    source: str
    weight: float = Field(ge=0.0, le=100.0)
    detail: str = ""


class DetectedOrganization(BaseModel):
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    llm_assisted: bool = False


class ExtractedEntity(BaseModel):
    name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    frequency: int = 0
    pages: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class PageCategory(BaseModel):
    category: str
    url: str
    title: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)


class WebsiteHierarchy(BaseModel):
    categories: list[PageCategory] = Field(default_factory=list)
    menu_links: list[str] = Field(default_factory=list)
    preset_seed: str = "generic_corporate"
    preset_confidence: float = 0.5
    preset_secondary: str = ""


class DiscoveredTopic(BaseModel):
    id: str
    title: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    page_count: int = 0
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    preferred_content_hints: list[str] = Field(default_factory=list)
    preferred_document_types: list[str] = Field(default_factory=list)
    answer_strategy: str = "generic"
    cluster_key: str = ""


class ContentHintCandidate(BaseModel):
    hint_id: str
    patterns: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    page_count: int = 0


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"] = "warning"
    code: str
    message: str
    field: str = ""
    auto_repaired: bool = False


class SiteStatistics(BaseModel):
    indexed_page_count: int = 0
    indexed_file_count: int = 0
    total_chunks: int = 0
    site_url: str = ""
    top_url_segments: list[str] = Field(default_factory=list)
    document_type_counts: dict[str, int] = Field(default_factory=dict)
    heading_counts: dict[str, int] = Field(default_factory=dict)
    language_guess: str = ""
    country_guess: str = ""
    currency_mentions: list[str] = Field(default_factory=list)


class KnowledgeGraphNode(BaseModel):
    node_id: str
    label: str
    node_type: str
    weight: float = 1.0
    page_urls: list[str] = Field(default_factory=list)


class KnowledgeGraph(BaseModel):
    nodes: list[KnowledgeGraphNode] = Field(default_factory=list)
    edges: list[tuple[str, str, str]] = Field(default_factory=list)


class PageMetadata(BaseModel):
    url: str
    title: str = ""
    meta_title: str = ""
    meta_description: str = ""
    h1: str = ""
    h2_list: list[str] = Field(default_factory=list)
    breadcrumbs: list[str] = Field(default_factory=list)
    canonical_url: str = ""
    path_segments: list[str] = Field(default_factory=list)
    schema_org_names: list[str] = Field(default_factory=list)
    og_site_name: str = ""
    json_ld_names: list[str] = Field(default_factory=list)
    copyright_lines: list[str] = Field(default_factory=list)
    footer_text: str = ""
    navigation_labels: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    organization_mentions: list[str] = Field(default_factory=list)
    product_names: list[str] = Field(default_factory=list)
    service_names: list[str] = Field(default_factory=list)
    branch_mentions: list[str] = Field(default_factory=list)
    atm_mentions: list[str] = Field(default_factory=list)
    language: str = ""
    country: str = ""
    currency: str = ""


class MetadataDataset(BaseModel):
    pages: list[PageMetadata] = Field(default_factory=list)
    site_url: str = ""
    aggregated_phones: list[str] = Field(default_factory=list)
    aggregated_emails: list[str] = Field(default_factory=list)
    aggregated_org_mentions: dict[str, int] = Field(default_factory=dict)


class GenerationReport(BaseModel):
    pages_analyzed: int = 0
    entities_extracted: int = 0
    topics_discovered: int = 0
    hints_generated: int = 0
    warnings: list[str] = Field(default_factory=list)
    llm_tokens: int = 0
    llm_used: bool = False
    generation_seconds: float = 0.0
    validator_fixes: int = 0
    confidence_distribution: dict[str, float] = Field(default_factory=dict)
    stage_timings: dict[str, float] = Field(default_factory=dict)


@dataclass
class PageRecord:
    """In-memory aggregate of one indexed page."""

    source_id: int
    url: str
    title: str
    document_type: str
    path_segments: list[str]
    headings: list[str]
    texts: list[str]
    content_hints: list[str]
    is_homepage: bool = False


@dataclass
class PipelineContext:
    """Mutable state passed through pipeline stages."""

    pages: list[PageRecord] = field(default_factory=list)
    site_url: str = ""
    metadata: MetadataDataset | None = None
    hierarchy: WebsiteHierarchy | None = None
    statistics: SiteStatistics | None = None
    knowledge_graph: KnowledgeGraph | None = None
    organization: DetectedOrganization | None = None
    entities: list[ExtractedEntity] = field(default_factory=list)
    topics: list[DiscoveredTopic] = field(default_factory=list)
    hint_candidates: list[ContentHintCandidate] = field(default_factory=list)
    document_type_rules: list[DocumentTypeRule] = field(default_factory=list)
    profile: KnowledgeProfile | None = None
    validation_issues: list[ValidationIssue] = field(default_factory=list)
    report: GenerationReport = field(default_factory=GenerationReport)
    extras: dict[str, Any] = field(default_factory=dict)


class AssembledProfile(BaseModel):
    profile: KnowledgeProfile
    organization: DetectedOrganization
    topics: list[DiscoveredTopic]
    hint_candidates: list[ContentHintCandidate]
    entities: list[ExtractedEntity]
    hierarchy: WebsiteHierarchy
    statistics: SiteStatistics
    overview_patterns: list[str] = Field(default_factory=list)
    query_expansion_rules: list[QueryExpansionRule] = Field(default_factory=list)
    source_priority_rules: list[SourcePriorityRule] = Field(default_factory=list)
