"""Adversarial regressions for corpus-grounded Knowledge Profile generation."""
from __future__ import annotations

import json

import pytest

from app.schemas.knowledge_profile import ImportantTopic
from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.knowledge_profile_generation.content_hint_discovery import (
    ContentHintDiscovery,
)
from app.services.knowledge_profile_generation.metadata_extractor import (
    WebsiteMetadataExtractor,
)
from app.services.knowledge_profile_generation.llm_refiner import LlmRefiner
from app.services.knowledge_profile_generation.lexical_grounding import labels_overlap
from app.services.knowledge_profile_generation.models import (
    MetadataDataset,
    PageRecord,
    WebsiteHierarchy,
)
from app.services.knowledge_profile_generation.organization_detector import (
    OrganizationDetector,
)
from app.services.knowledge_profile_generation.site_identity import (
    infer_site_identity,
    is_grounded_in_evidence,
)
from app.services.knowledge_profile_generation.structure_analyzer import (
    WebsiteStructureAnalyzer,
)
from app.services.knowledge_profile_generation.topic_discovery import TopicDiscovery
from app.services.knowledge_understanding.models import Concept, EvidenceLink
from app.services.knowledge_profile_service import generic_corporate_profile


def _page(
    source_id: int,
    url: str,
    title: str,
    *,
    texts: list[str] | None = None,
    headings: list[str] | None = None,
    hints: list[str] | None = None,
    semantic: SourceSemanticProfile | None = None,
    is_homepage: bool = False,
) -> PageRecord:
    path = url.split("://", 1)[-1].partition("/")[2]
    return PageRecord(
        source_id=source_id,
        url=url,
        title=title,
        document_type="generic_page",
        path_segments=[part for part in path.split("/") if part],
        headings=headings or [title],
        texts=texts or [title],
        content_hints=hints or [],
        is_homepage=is_homepage,
        main_text=" ".join(texts or [title]),
        semantic_profile=semantic,
    )


@pytest.mark.unit
def test_page_heading_cannot_outvote_corpus_hostname_for_organization():
    pages = [
        _page(
            1,
            "https://ukrsibbank.com/",
            "UKRSIBBANK",
            texts=["UKRSIBBANK"],
            is_homepage=True,
        )
    ]
    pages.extend(
        _page(
            source_id,
            f"https://ukrsibbank.com/about/page-{source_id}",
            "About the organization",
            texts=["General information"],
        )
        for source_id in range(2, 62)
    )

    metadata = WebsiteMetadataExtractor().extract(pages, site_url="")
    hierarchy = WebsiteStructureAnalyzer().analyze(pages, metadata)
    detected = OrganizationDetector().detect(metadata, pages, hierarchy)

    assert metadata.site_url == "https://ukrsibbank.com"
    assert detected.name.casefold() == "ukrsibbank"
    assert detected.name != "About the organization"


@pytest.mark.unit
def test_subject_never_matches_arbitrary_first_word_of_bad_identity():
    page = _page(
        1,
        "https://example.com/",
        "Home",
        texts=[
            "We remind you about the temporary unavailability of services.",
        ],
        is_homepage=True,
    )
    identity = infer_site_identity(
        organization_name="About the organization",
        pages=[page],
        metadata=MetadataDataset(),
        hierarchy=None,
        top_url_segments=[],
        topic_labels=["Client services", "Digital products"],
    )

    assert "temporary unavailability" not in identity.site_subject
    assert identity.site_subject.startswith("About the organization —")


@pytest.mark.unit
def test_topics_reuse_understanding_and_reject_document_purpose_cluster():
    news_semantic = SourceSemanticProfile(
        main_topic="News Post",
        main_topic_confidence=0.9,
        document_purpose="News Post",
        document_purpose_confidence=0.95,
        confidence=0.9,
    )
    topic_semantic = SourceSemanticProfile(
        main_topic="Payment cards",
        main_topic_confidence=0.88,
        document_purpose="Service description",
        document_purpose_confidence=0.9,
        confidence=0.88,
    )
    pages = [
        *[
            _page(
                source_id,
                f"https://example.com/news/{source_id}",
                f"Update {source_id}",
                semantic=news_semantic,
            )
            for source_id in range(1, 11)
        ],
        *[
            _page(
                source_id,
                f"https://example.com/cards/{source_id}",
                f"Card {source_id}",
                semantic=topic_semantic,
            )
            for source_id in range(11, 15)
        ],
        *[
            _page(
                source_id,
                f"https://example.com/deposits/{source_id}",
                f"Deposit {source_id}",
                semantic=topic_semantic.model_copy(
                    update={"main_topic": "Savings accounts"}
                ),
            )
            for source_id in range(15, 19)
        ],
    ]
    concepts = [
        Concept("news-post", "News Post", confidence=0.92, evidence_count=10),
        Concept("payment-cards", "Payment cards", confidence=0.88, evidence_count=4),
        Concept("savings-accounts", "Savings accounts", confidence=0.87, evidence_count=4),
    ]
    evidence = [
        *[EvidenceLink("news-post", source_id, "explains", 0.9, 0.9) for source_id in range(1, 11)],
        *[
            EvidenceLink("payment-cards", source_id, "explains", 0.88, 0.88)
            for source_id in range(11, 15)
        ],
        *[
            EvidenceLink("savings-accounts", source_id, "explains", 0.87, 0.87)
            for source_id in range(15, 19)
        ],
    ]

    topics = TopicDiscovery().discover(
        pages,
        WebsiteHierarchy(),
        entities=[],
        organization_name="Example",
        understanding_concepts=concepts,
        understanding_evidence=evidence,
    )
    labels = {topic.title for topic in topics}

    assert labels == {"Payment cards", "Savings accounts"}
    assert all(topic.evidence[0].source == "knowledge_understanding" for topic in topics)


@pytest.mark.unit
def test_content_hints_drop_singletons_and_are_output_bounded():
    pages = [
        _page(
            source_id,
            f"https://example.com/page-{source_id}",
            f"Page {source_id}",
            hints=[f"one_off_{source_id}", "repeated" if source_id <= 12 else ""],
        )
        for source_id in range(1, 201)
    ]
    discovery = ContentHintDiscovery()
    hints = discovery.discover(pages, WebsiteHierarchy(), topics=[])
    ids = {hint.hint_id for hint in hints}

    assert ids == {"repeated", "generic"}
    assert len(hints) <= 24


@pytest.mark.unit
def test_llm_refiner_applies_only_compact_existing_topic_patch():
    profile = generic_corporate_profile()
    profile.site_subject = "Old subject"
    profile.entity_type = "Old type"
    profile.important_topics = [
        ImportantTopic(key="a", label="Topic A"),
        ImportantTopic(key="b", label="Topic B"),
    ]
    response = """
    ```json
    {
      "site_subject": "Grounded subject",
      "entity_type": "Grounded type",
      "topic_keys": ["b", "b", "invented"],
      "topic_labels": {"b": "Better B", "invented": "No"}
    }
    ```
    """

    data = LlmRefiner._json_object(response)
    patched = LlmRefiner._apply_patch(profile, json.loads(data))

    assert patched.site_subject == "Grounded subject"
    assert patched.entity_type == "Grounded type"
    assert [(topic.key, topic.label) for topic in patched.important_topics] == [
        ("b", "Better B")
    ]
    assert profile.site_subject == "Old subject"


@pytest.mark.unit
def test_identity_uses_homepage_si_type_over_relationship_phrase():
    semantic = SourceSemanticProfile(
        entity_type="organization",
        entity_type_confidence=0.95,
        confidence=0.9,
    )
    page = _page(
        1,
        "https://example.com/",
        "Example",
        texts=["Example is part of an international group."],
        semantic=semantic,
        is_homepage=True,
    )
    identity = infer_site_identity(
        organization_name="Example",
        pages=[page],
        metadata=None,
        hierarchy=None,
        top_url_segments=[],
    )

    assert identity.entity_type == "organization"
    assert identity.entity_type_source == "source_intelligence"


@pytest.mark.unit
def test_lexical_grounding_dedupes_inflections_without_domain_dictionary():
    assert labels_overlap("Banking Services", "Bank Services")
    assert not labels_overlap("Banking Services", "Banking Regulations")
    assert is_grounded_in_evidence("bank", ["Banking services for customers"])


@pytest.mark.unit
def test_generic_si_purpose_falls_back_to_repeated_chunk_hint():
    semantic = SourceSemanticProfile(
        document_purpose="generic",
        document_purpose_confidence=0.9,
        confidence=0.9,
    )
    pages = [
        _page(
            source_id,
            f"https://example.com/{source_id}",
            f"Page {source_id}",
            hints=["observed_hint"],
            semantic=semantic,
        )
        for source_id in range(1, 6)
    ]
    hints = ContentHintDiscovery().discover(pages, WebsiteHierarchy(), topics=[])

    assert {hint.hint_id for hint in hints} == {"observed_hint", "generic"}


@pytest.mark.unit
def test_weak_understanding_concepts_do_not_bypass_corpus_support_gate():
    pages = [
        _page(
            source_id,
            f"https://example.com/{source_id}",
            f"Page {source_id}",
            semantic=SourceSemanticProfile(
                document_purpose="single purpose",
                confidence=0.9,
            ),
        )
        for source_id in range(1, 401)
    ]
    concepts = [
        Concept("weak-a", "Weak A", confidence=0.9, evidence_count=2),
        Concept("weak-b", "Weak B", confidence=0.9, evidence_count=2),
    ]
    evidence = [
        EvidenceLink("weak-a", 1, "explains", 0.9, 0.9),
        EvidenceLink("weak-a", 2, "explains", 0.9, 0.9),
        EvidenceLink("weak-b", 3, "explains", 0.9, 0.9),
        EvidenceLink("weak-b", 4, "explains", 0.9, 0.9),
    ]

    topics = TopicDiscovery()._from_understanding(
        pages,
        concepts,
        evidence,
        organization_name="Example",
    )

    assert topics == []
