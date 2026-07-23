"""Tests for deterministic Knowledge Profile generation pipeline."""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db
from app.models.chunk import Chunk
from app.models.source import Source
from app.repositories.settings_repository import SettingsRepository
from app.services.knowledge_profile_generation.alias_utils import dedupe_topic_aliases
from app.services.knowledge_profile_generation.auto_repair import ProfileAutoRepair
from app.services.knowledge_profile_generation.confidence_engine import ConfidenceEngine
from app.services.knowledge_profile_generation.content_hint_discovery import (
    ContentHintDiscovery,
)
from app.services.knowledge_profile_generation.entity_extractor import EntityExtractor
from app.services.knowledge_profile_generation.metadata_extractor import (
    WebsiteMetadataExtractor,
)
from app.services.knowledge_profile_generation.models import EvidenceItem, PageRecord
from app.services.knowledge_profile_generation.organization_detector import (
    OrganizationDetector,
)
from app.services.knowledge_profile_generation.pipeline import KnowledgeProfilePipeline
from app.services.knowledge_profile_generation.structure_analyzer import (
    WebsiteStructureAnalyzer,
)
from app.services.knowledge_profile_generation.topic_discovery import TopicDiscovery
from app.services.knowledge_profile_generation.validator import KnowledgeProfileValidator
from app.services.knowledge_profile_generator_service import (
    KnowledgeProfileGeneratorService,
)
from app.schemas.knowledge_profile import ImportantTopic
from app.services.knowledge_profile_service import generic_corporate_profile
from app.utils.time_utils import utcnow


@pytest.fixture()
def db() -> Session:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _page(
    url: str,
    title: str,
    *,
    segments: list[str] | None = None,
    headings: list[str] | None = None,
    texts: list[str] | None = None,
    is_homepage: bool = False,
    hints: list[str] | None = None,
) -> PageRecord:
    return PageRecord(
        source_id=hash(url) % 100000,
        url=url,
        title=title,
        document_type="generic_page",
        path_segments=segments or [],
        headings=headings or [],
        texts=texts or [],
        content_hints=hints or ["generic"],
        is_homepage=is_homepage,
    )


def _ukrsibbank_pages() -> list[PageRecord]:
    footer = "© UKRSIBBANK 2024. All rights reserved."
    return [
        _page(
            "https://ukrsibbank.com/",
            "UKRSIBBANK — Universal Bank",
            segments=[],
            headings=["Welcome to UKRSIBBANK"],
            texts=[footer, "UKRSIBBANK offers credit cards and deposits."],
            is_homepage=True,
            hints=["about"],
        ),
        _page(
            "https://ukrsibbank.com/about",
            "About UKRSIBBANK",
            segments=["about"],
            headings=["About UKRSIBBANK"],
            texts=["UKRSIBBANK is a leading bank in Ukraine.", footer],
            hints=["about"],
        ),
        _page(
            "https://ukrsibbank.com/contacts",
            "Contacts",
            segments=["contacts"],
            headings=["Contact UKRSIBBANK"],
            texts=["Phone: +380 44 123 4567", footer],
            hints=["contacts"],
        ),
        _page(
            "https://ukrsibbank.com/rates",
            "Exchange Rates",
            segments=["rates"],
            headings=["Currency exchange rates"],
            texts=["USD/EUR/UAH exchange rates table", footer],
            hints=["rates"],
        ),
        _page(
            "https://ukrsibbank.com/cards",
            "Credit Cards",
            segments=["cards"],
            headings=["Visa and Mastercard cards"],
            texts=["Premium credit card products", footer],
            hints=["products"],
        ),
        _page(
            "https://ukrsibbank.com/loans",
            "Loans",
            segments=["loans"],
            headings=["Consumer loans"],
            texts=["Mortgage and auto loan", footer],
            hints=["products"],
        ),
        _page(
            "https://ukrsibbank.com/branches",
            "Branches and ATMs",
            segments=["branches"],
            headings=["Branch locator"],
            texts=["Find branch and ATM locations", footer],
            hints=["contacts"],
        ),
        _page(
            "https://ukrsibbank.com/branches/kyiv-1",
            "Branch Kyiv",
            segments=["branches", "kyiv-1"],
            headings=["Kyiv branch"],
            texts=["Branch address Kyiv", footer],
            hints=["contacts"],
        ),
    ]


def _seed_indexed_site(db: Session, *, pages: int = 15) -> None:
    settings = SettingsRepository(db).get_or_create()
    settings.site_url = "https://example.com"
    db.add(settings)
    now = utcnow()
    suffix = uuid.uuid4().hex[:8]
    for i in range(pages):
        src = Source(
            url=f"https://example.com/{suffix}/section/page-{i}",
            source_type="page",
            title=f"Example Page {i}",
            status="indexed",
            document_type="generic_page",
            next_refresh_at=now + timedelta(hours=72),
        )
        db.add(src)
        db.flush()
        db.add(
            Chunk(
                source_id=src.id,
                chunk_index=0,
                title=src.title,
                url=src.url,
                text=f"Products and delivery information block {i}",
                content_type_hint="products" if i % 3 == 0 else "generic",
                document_type="generic_page",
            )
        )
    db.commit()


def _seed_ukrsibbank(db: Session) -> None:
    settings = SettingsRepository(db).get_or_create()
    settings.site_url = "https://ukrsibbank.com"
    db.add(settings)
    now = utcnow()
    suffix = uuid.uuid4().hex[:6]
    for page in _ukrsibbank_pages():
        path = page.url.replace("https://ukrsibbank.com", "")
        url = f"https://ukrsibbank.com/test-{suffix}{path or '/'}"
        src = Source(
            url=url,
            source_type="page",
            title=page.title,
            status="indexed",
            document_type="generic_page",
            next_refresh_at=now + timedelta(hours=72),
        )
        db.add(src)
        db.flush()
        for i, text in enumerate(page.texts or [""]):
            db.add(
                Chunk(
                    source_id=src.id,
                    chunk_index=i,
                    title=page.title,
                    url=url,
                    text=text,
                    heading=page.headings[i] if i < len(page.headings) else None,
                    content_type_hint=page.content_hints[i % len(page.content_hints)],
                    document_type="generic_page",
                    is_homepage=page.is_homepage,
                )
            )
    db.commit()


class TestMetadataExtractor:
    def test_extracts_phones_and_org_mentions(self):
        pages = _ukrsibbank_pages()
        meta = WebsiteMetadataExtractor().extract(pages, "https://ukrsibbank.com")
        assert meta.aggregated_phones
        assert any("UKRSIBBANK" in k for k in meta.aggregated_org_mentions)


class TestOrganizationDetector:
    def test_detects_ukrsibbank_not_branches(self):
        pages = _ukrsibbank_pages()
        meta = WebsiteMetadataExtractor().extract(pages, "https://ukrsibbank.com")
        hierarchy = WebsiteStructureAnalyzer().analyze(pages, meta)
        org = OrganizationDetector().detect(meta, pages, hierarchy)
        assert "UKRSIBBANK" in org.name.upper()
        assert "branches and atms" not in org.name.lower()
        assert org.confidence >= 0.5
        assert any(e.source in ("footer", "footer_copyright", "homepage", "frequency") for e in org.evidence)


class TestTopicDiscovery:
    def test_no_generic_only_topics(self):
        pages = _ukrsibbank_pages()
        meta = WebsiteMetadataExtractor().extract(pages, "https://ukrsibbank.com")
        hierarchy = WebsiteStructureAnalyzer().analyze(pages, meta)
        entities = EntityExtractor().extract(pages, meta, organization_name="UKRSIBBANK")
        topics = TopicDiscovery().discover(
            pages, hierarchy, entities, organization_name="UKRSIBBANK"
        )
        titles = {t.title.lower() for t in topics}
        assert "general" not in titles
        assert "products" not in titles or any(t.page_count >= 2 for t in topics if t.title.lower() == "products")
        assert len(topics) >= 3


class TestContentHintDiscovery:
    def test_unknown_hint_prevention(self):
        pages = _ukrsibbank_pages()
        meta = WebsiteMetadataExtractor().extract(pages, "https://ukrsibbank.com")
        hierarchy = WebsiteStructureAnalyzer().analyze(pages, meta)
        entities = EntityExtractor().extract(pages, meta)
        topics = TopicDiscovery().discover(pages, hierarchy, entities)
        discovery = ContentHintDiscovery()
        hints = discovery.discover(pages, hierarchy, topics)
        registered = discovery.registered_ids()
        assert "rates" in registered or "contacts" in registered
        fixed_topics = discovery.validate_topic_hints(topics)
        for topic in fixed_topics:
            for hint in topic.preferred_content_hints:
                assert hint in registered


class TestValidator:
    def test_rejects_unknown_content_hint(self):
        profile = generic_corporate_profile()
        profile.important_topics.append(
            ImportantTopic(key="test_topic", label="Test Topic", preferred_content_hints=[])
        )
        profile.important_topics[-1].preferred_content_hints = ["nonexistent_hint_xyz"]
        issues = KnowledgeProfileValidator().validate(profile)
        assert any(i.code == "unknown_content_hint" for i in issues)


class TestAutoRepair:
    def test_creates_missing_hint(self):
        profile = generic_corporate_profile()
        profile.important_topics.append(
            ImportantTopic(key="test_topic", label="Test Topic", preferred_content_hints=[])
        )
        profile.important_topics[-1].preferred_content_hints = ["custom_hint"]
        issues = KnowledgeProfileValidator().validate(profile)
        repaired, _, fixes = ProfileAutoRepair().repair(profile, issues)
        hint_ids = {r.content_type_hint for r in repaired.content_hint_rules}
        assert fixes >= 1
        assert "custom_hint" in hint_ids or not any(
            "custom_hint" in t.preferred_content_hints for t in repaired.important_topics
        )

    def test_dedupes_duplicate_aliases(self):
        profile = generic_corporate_profile()
        profile.important_topics = [
            ImportantTopic(key="news", label="News", aliases=["news", "новини"]),
            ImportantTopic(key="about", label="About", aliases=["about", "news", "про нас"]),
            ImportantTopic(key="rates", label="Rates", aliases=["rates", "курси"]),
        ]
        issues = KnowledgeProfileValidator().validate(profile)
        assert any(i.code == "duplicate_alias" for i in issues)
        repaired, _, fixes = ProfileAutoRepair().repair(profile, issues)
        assert fixes >= 1
        all_aliases: list[str] = []
        for topic in repaired.important_topics:
            for alias in topic.aliases:
                assert alias.lower() not in all_aliases
                all_aliases.append(alias.lower())
        remaining_issues = KnowledgeProfileValidator().validate(repaired)
        assert not any(i.code == "duplicate_alias" for i in remaining_issues)


class TestAliasUtils:
    def test_dedupe_keeps_first_occurrence(self):
        profile = generic_corporate_profile()
        profile.important_topics = [
            ImportantTopic(key="cards", label="Cards", aliases=["cards", "картки"]),
            ImportantTopic(key="loans", label="Loans", aliases=["loans", "cards"]),
        ]
        deduped, removed = dedupe_topic_aliases(profile)
        assert removed == 1
        assert "cards" in deduped.important_topics[0].aliases
        assert "cards" not in deduped.important_topics[1].aliases
        assert "loans" in deduped.important_topics[1].aliases


class TestConfidenceEngine:
    def test_organization_score_from_evidence(self):
        engine = ConfidenceEngine()
        score = engine.organization_score(
            [
                EvidenceItem(source="schema.org", weight=40),
                EvidenceItem(source="footer", weight=20),
                EvidenceItem(source="homepage", weight=15),
            ]
        )
        assert score >= 0.7


class TestEntityExtractor:
    def test_extracts_currencies_and_products(self):
        pages = _ukrsibbank_pages()
        meta = WebsiteMetadataExtractor().extract(pages, "https://ukrsibbank.com")
        entities = EntityExtractor().extract(pages, meta, organization_name="UKRSIBBANK")
        types = {e.entity_type for e in entities}
        assert "product" in types or "service" in types or "currency" in types


class TestPipelineIntegration:
    def test_generator_produces_valid_profile(self, db: Session):
        _seed_indexed_site(db, pages=15)
        gen = KnowledgeProfileGeneratorService(db)
        preview, analytics = gen.generate(use_llm=False)
        assert preview.profile is not None
        assert preview.organization is not None
        assert len(preview.profile.important_topics) >= 1
        assert analytics["llm_used"] is False

    def test_ukrsibbank_regression(self, db: Session):
        _seed_ukrsibbank(db)
        pipeline = KnowledgeProfilePipeline(db)
        preview, analytics = pipeline.run(use_llm=False)
        assert preview.organization is not None
        assert "UKRSIBBANK" in preview.organization.value.upper()
        assert "branches and atms" not in preview.organization.value.lower()
        profile = preview.profile
        assert profile is not None
        hint_ids = {r.content_type_hint for r in profile.content_hint_rules}
        for topic in profile.important_topics:
            for hint in topic.preferred_content_hints:
                assert hint in hint_ids, f"Unknown hint {hint} on topic {topic.key}"
        assert preview.content_hints
        assert preview.analytics
        # Organization should be evidence-based
        assert preview.organization.detail
        duplicate_warnings = [w for w in preview.warnings if "Duplicate alias" in w]
        assert not duplicate_warnings, duplicate_warnings


def test_generation_api_start(client, auth_headers, db: Session):
    _seed_indexed_site(db, pages=10)
    res = client.post(
        "/api/knowledge-profile/generate/start",
        headers=auth_headers,
        json={"use_llm": False, "merge_identity": False},
    )
    assert res.status_code == 200

    import time

    for _ in range(40):
        st = client.get("/api/knowledge-profile/generate/status", headers=auth_headers)
        if st.json()["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)
    final = st.json()
    assert final["status"] == "completed"
    assert final["preview"]["profile"] is not None
