"""Agent Knowledge Profile — domain-agnostic retrieval configuration."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AnswerStrategy = Literal[
    "overview",
    "fact",
    "list",
    "table",
    "contact",
    "pricing",
    "comparison",
    "step_by_step",
    "faq",
    "troubleshooting",
    "generic",
]

RoutingIntent = Literal[
    "entity_overview",
    "topic_overview",
    "category_overview",
    "specific_fact",
    "faq_like",
    "contacts_query",
    "news_query",
    "unknown",
]


class IntentRule(BaseModel):
    key: str = Field(min_length=1)
    label: str = ""
    patterns: list[str] = Field(default_factory=list)
    topic_key: str | None = None
    topic_required: bool = False
    routing_intent: RoutingIntent = "unknown"
    default_answer_strategy: AnswerStrategy = "generic"
    priority: int = Field(default=50, ge=0, le=1000)


class ImportantTopic(BaseModel):
    key: str = Field(min_length=1)
    label: str = ""
    aliases: list[str] = Field(default_factory=list)
    preferred_document_types: list[str] = Field(default_factory=list)
    preferred_content_hints: list[str] = Field(default_factory=list)
    answer_strategy: AnswerStrategy = "generic"


class DocumentTypeRule(BaseModel):
    document_type: str = Field(min_length=1)
    url_patterns: list[str] = Field(default_factory=list)
    title_patterns: list[str] = Field(default_factory=list)
    heading_patterns: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=1000)


class ContentHintRule(BaseModel):
    content_type_hint: str = Field(min_length=1)
    patterns: list[str] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0, le=1000)


class SourcePriorityRule(BaseModel):
    query_intent: str = Field(min_length=1)
    boost_document_types: list[str] = Field(default_factory=list)
    deprioritize_document_types: list[str] = Field(default_factory=list)
    boost_content_hints: list[str] = Field(default_factory=list)
    deprioritize_content_hints: list[str] = Field(default_factory=list)
    score_boost: float = Field(default=0.35, ge=0.0, le=1.0)


class QueryExpansionRule(BaseModel):
    trigger_patterns: list[str] = Field(default_factory=list)
    add_terms: list[str] = Field(default_factory=list)
    intent: str | None = None
    trigger_intent: str | None = None


class KnowledgeProfile(BaseModel):
    site_display_name: str = ""
    organization_name: str = ""
    organization_aliases: list[str] = Field(default_factory=list)
    site_subject: str = ""
    entity_type: str = ""

    overview_query_patterns: list[str] = Field(default_factory=list)
    intents: list[IntentRule] = Field(default_factory=list)
    important_topics: list[ImportantTopic] = Field(default_factory=list)
    document_type_rules: list[DocumentTypeRule] = Field(default_factory=list)
    content_hint_rules: list[ContentHintRule] = Field(default_factory=list)
    source_priority_rules: list[SourcePriorityRule] = Field(default_factory=list)
    query_expansion_rules: list[QueryExpansionRule] = Field(default_factory=list)


class AppliedKnowledgeConfig(BaseModel):
    detected_intent: str = "unknown"
    matched_intent_key: str | None = None
    matched_intent_label: str | None = None
    answer_strategy: AnswerStrategy = "generic"
    matched_topic_key: str | None = None
    matched_topic_label: str | None = None
    matched_aliases: list[str] = Field(default_factory=list)
    matched_patterns: list[str] = Field(default_factory=list)
    query_expansions: list[str] = Field(default_factory=list)
    boosted_document_types: list[str] = Field(default_factory=list)
    deprioritized_document_types: list[str] = Field(default_factory=list)
    boosted_content_hints: list[str] = Field(default_factory=list)
    deprioritized_content_hints: list[str] = Field(default_factory=list)
    supplemental_queries: list[str] = Field(default_factory=list)
    no_answer_reason: str | None = None
