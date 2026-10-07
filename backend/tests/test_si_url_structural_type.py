"""SI URL structural type / purpose coercion (Wave B quality)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.source_intelligence_service import SourceIntelligenceService

pytestmark = pytest.mark.unit


def test_url_structural_news_and_campaign() -> None:
    assert (
        SourceIntelligenceService._url_structural_document_type(
            "https://example.com/news-post/foo"
        )
        == "news_page"
    )
    assert (
        SourceIntelligenceService._url_structural_document_type(
            "https://example.com/en/blog/bar"
        )
        == "news_page"
    )
    assert (
        SourceIntelligenceService._url_structural_document_type(
            "https://example.com/campaign/summer"
        )
        == "campaign_page"
    )
    assert (
        SourceIntelligenceService._url_structural_document_type(
            "https://example.com/about"
        )
        is None
    )


def test_coerce_purpose_overrides_llm_about_on_news() -> None:
    sem = SourceSemanticProfile(
        document_purpose="about page",
        document_purpose_confidence=0.98,
        main_topic="X",
    )
    out = SourceIntelligenceService._coerce_purpose_for_document_type(
        sem, document_type="news_page"
    )
    assert out.document_purpose == "news"
    assert out.document_purpose_confidence >= 0.9


def test_news_purpose_not_canonical() -> None:
    from app.services.knowledge_profile_service import KnowledgeProfileService

    assert (
        SourceIntelligenceService._is_canonical(
            url="https://example.com/news-post/x",
            title="News",
            document_type="news_page",
            is_homepage=False,
            profile=KnowledgeProfileService.default_profile(),
            content_quality=80,
            document_purpose="news",
        )
        is False
    )
