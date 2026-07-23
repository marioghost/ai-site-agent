"""Source Intelligence semantic profile schema (domain-agnostic)."""
from __future__ import annotations

from pydantic import BaseModel, Field


GENERIC_DOCUMENT_PURPOSES = frozenset({
    "product listing",
    "product details",
    "service description",
    "legal information",
    "documentation",
    "faq",
    "contact information",
    "news",
    "promotion",
    "landing page",
    "about company",
    "support",
    "policy",
    "comparison",
    "pricing",
    "general information",
})

GENERIC_ENTITY_TYPES = frozenset({
    "product",
    "service",
    "branch",
    "person",
    "organization",
    "policy",
    "faq",
    "promotion",
    "document",
    "article",
    "category",
})

GENERIC_SUPPORTED_INTENTS = frozenset({
    "overview",
    "listing",
    "comparison",
    "pricing",
    "eligibility",
    "requirements",
    "contacts",
    "support",
    "troubleshooting",
    "legal",
    "documentation",
    "faq",
    "entity_overview",
    "topic_overview",
    "category_overview",
    "specific_fact",
    "faq_like",
    "contacts_query",
    "news_query",
    "product_query",
})


class SourceSemanticProfile(BaseModel):
    """Rich semantic document profile generated at index time."""

    main_topic: str = ""
    main_topic_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    subtopics: list[str] = Field(default_factory=list, max_length=12)
    document_purpose: str = ""
    document_purpose_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    entity_type: str = ""
    entity_type_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supported_intents: list[str] = Field(default_factory=list, max_length=16)
    search_keywords: list[str] = Field(default_factory=list, max_length=24)
    synonyms: list[str] = Field(default_factory=list, max_length=24)
    semantic_tags: list[str] = Field(default_factory=list, max_length=20)
    suitable_for: list[str] = Field(default_factory=list, max_length=12)
    not_suitable_for: list[str] = Field(default_factory=list, max_length=12)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    generator: str = "rules"
    generated_at: str | None = None

    def to_storage_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_storage(cls, data: dict | None) -> SourceSemanticProfile | None:
        if not data:
            return None
        try:
            return cls.model_validate(data)
        except ValueError:
            return None
