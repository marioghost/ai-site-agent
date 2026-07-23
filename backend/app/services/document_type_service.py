"""Configurable document/page type classification during indexing."""
from __future__ import annotations

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.content_signals import is_homepage_url
from app.services.knowledge_profile_service import KnowledgeProfileService

DocumentType = str


def detect_document_type(
    *,
    url: str,
    title: str = "",
    headings: str = "",
    source_type: str = "page",
    profile: KnowledgeProfile | None = None,
) -> DocumentType:
    profile = profile or KnowledgeProfileService.default_profile()
    return KnowledgeProfileService.match_document_type(
        profile,
        url=url,
        title=title,
        headings=headings,
        source_type=source_type,
        is_homepage=is_homepage_url(url),
    )
