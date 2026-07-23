"""Tests for Knowledge Profile AI generator."""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db
from app.models.chunk import Chunk
from app.models.source import Source
from app.repositories.settings_repository import SettingsRepository
from app.services.knowledge_profile_generator_service import (
    KnowledgeProfileGeneratorService,
)
from app.services.knowledge_profile_site_analyzer import KnowledgeProfileSiteAnalyzer
from app.utils.time_utils import utcnow


@pytest.fixture()
def db() -> Session:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


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


def test_site_analyzer_prereq_errors(db: Session):
    analyzer = KnowledgeProfileSiteAnalyzer(
        db, SettingsRepository(db).get_or_create()
    )
    errors = analyzer.prereq_errors()
    if analyzer.analyze().indexed_page_count == 0:
        assert errors
        assert "indexed pages" in errors[0].lower()
    else:
        assert errors == []


def test_generator_produces_valid_profile(db: Session):
    _seed_indexed_site(db, pages=15)
    gen = KnowledgeProfileGeneratorService(db)
    preview, analytics = gen.generate(use_llm=False)
    assert preview.profile is not None
    assert preview.organization is not None
    assert preview.website_type is not None
    assert len(preview.profile.important_topics) >= 1
    assert analytics["llm_used"] is False


def test_generation_api_start(client, auth_headers, db: Session):
    _seed_indexed_site(db, pages=10)
    res = client.post(
        "/api/knowledge-profile/generate/start",
        headers=auth_headers,
        json={"use_llm": False, "merge_identity": False},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("running", "completed")

    import time

    for _ in range(30):
        st = client.get("/api/knowledge-profile/generate/status", headers=auth_headers)
        if st.json()["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)
    final = st.json()
    assert final["status"] == "completed"
    assert final["preview"]["profile"] is not None
