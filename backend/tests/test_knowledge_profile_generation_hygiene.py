"""Unit tests for KP generation structural filters and assembler hygiene."""
from __future__ import annotations

import pytest

from app.schemas.knowledge_profile import ImportantTopic
from app.services.knowledge_profile_generation.models import (
    DetectedOrganization,
    DiscoveredTopic,
    MetadataDataset,
    PageRecord,
    PipelineContext,
    SiteStatistics,
    WebsiteHierarchy,
)
from app.services.knowledge_profile_generation.profile_assembler import ProfileAssembler
from app.services.knowledge_profile_generation.structural_filters import (
    derive_site_subject,
    first_meaningful_path_segment,
    is_locale_like_path_segment,
)
from app.services.knowledge_profile_generation.structure_analyzer import (
    WebsiteStructureAnalyzer,
)
from app.services.knowledge_profile_generation.topic_discovery import TopicDiscovery


def _page(
    *,
    source_id: int,
    url: str,
    title: str,
    path_segments: list[str],
    texts: list[str] | None = None,
    is_homepage: bool = False,
) -> PageRecord:
    return PageRecord(
        source_id=source_id,
        url=url,
        title=title,
        document_type="generic_page",
        path_segments=path_segments,
        headings=[title],
        texts=texts or [title],
        content_hints=[],
        is_homepage=is_homepage,
    )


@pytest.mark.unit
def test_locale_like_path_segments_are_structural():
    assert is_locale_like_path_segment("en")
    assert is_locale_like_path_segment("uk")
    assert is_locale_like_path_segment("en-us")
    assert not is_locale_like_path_segment("about")
    assert not is_locale_like_path_segment("private_individuals")
    assert first_meaningful_path_segment(["en", "about", "team"]) == "about"
    assert first_meaningful_path_segment(["en"]) is None


@pytest.mark.unit
def test_derive_site_subject_rejects_polluted_homepage():
    org = "UKRSIBBANK"
    polluted = (
        "UKRSIBBANK | Банківські послуги — 5% знижки з кредитною карткою "
        "в магазинах COMFYДеталі акції ще довгий промо текст"
    )
    assert derive_site_subject(organization_name=org, homepage_texts=[polluted]) == ""

    clean = "UKRSIBBANK provides banking services for teams."
    subject = derive_site_subject(organization_name=org, homepage_texts=[clean])
    assert "UKRSIBBANK" in subject
    assert "|" not in subject
    assert len(subject) <= 160


@pytest.mark.unit
def test_structure_analyzer_never_classifies_industry_preset():
    pages = [
        _page(
            source_id=1,
            url="https://example.com/en/cards/visa",
            title="Visa cards",
            path_segments=["en", "cards", "visa"],
            texts=["credit card bank loan deposit atm iban"],
        ),
        _page(
            source_id=2,
            url="https://example.com/",
            title="Home",
            path_segments=[],
            is_homepage=True,
        ),
    ]
    hierarchy = WebsiteStructureAnalyzer().analyze(pages, MetadataDataset())
    assert hierarchy.preset_seed == "generic_corporate"
    assert hierarchy.preset_secondary == ""
    cats = {c.url: c.category for c in hierarchy.categories}
    assert cats[pages[0].url] == "cards"
    assert cats[pages[1].url] == "homepage"


@pytest.mark.unit
def test_topic_discovery_skips_locale_clusters():
    pages = [
        _page(
            source_id=1,
            url="https://example.com/en/cards",
            title="Cards",
            path_segments=["en", "cards"],
            texts=["card products"],
        ),
        _page(
            source_id=2,
            url="https://example.com/en/cards/visa",
            title="Visa",
            path_segments=["en", "cards"],
            texts=["visa"],
        ),
        _page(
            source_id=3,
            url="https://example.com/en",
            title="En",
            path_segments=["en"],
            texts=["lang"],
        ),
    ]
    hierarchy = WebsiteHierarchy(
        categories=[],
        menu_links=[],
        preset_seed="generic_corporate",
    )
    topics = TopicDiscovery().discover(pages, hierarchy, entities=[], organization_name="Example")
    keys = {t.cluster_key.lower() for t in topics}
    assert "en" not in keys
    assert any("card" in k for k in keys)


@pytest.mark.unit
def test_assembler_uses_generic_base_not_industry_preset():
    org = DetectedOrganization(name="Acme", aliases=["Acme Corp"], confidence=0.9)
    hierarchy = WebsiteHierarchy(categories=[], menu_links=[], preset_seed="bank_financial")
    stats = SiteStatistics(
        indexed_page_count=3,
        indexed_file_count=0,
        total_chunks=3,
        site_url="https://example.com",
        top_url_segments=["about"],
        document_type_counts={},
    )
    ctx = PipelineContext(
        organization=org,
        hierarchy=hierarchy,
        statistics=stats,
        pages=[
            _page(
                source_id=1,
                url="https://example.com/",
                title="Home",
                path_segments=[],
                texts=["Acme builds software for teams."],
                is_homepage=True,
            )
        ],
        topics=[
            DiscoveredTopic(
                id="about",
                title="About",
                description="",
                aliases=["About"],
                page_count=2,
                confidence=0.8,
                evidence=[],
                preferred_content_hints=[],
                preferred_document_types=["category_page"],
                answer_strategy="generic",
                cluster_key="about",
            )
        ],
        hint_candidates=[],
        entities=[],
        extras={"hint_rules": [], "registered_hint_ids": set()},
    )
    assembled = ProfileAssembler().assemble(ctx)
    assert assembled.profile.entity_type == "organization"
    assert "банк" not in " ".join(assembled.profile.overview_query_patterns).lower()
    assert assembled.profile.site_subject.startswith("Acme")
    assert all(isinstance(t, ImportantTopic) for t in assembled.profile.important_topics)
