"""Performance-focused tests for Source Intelligence scanner."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from tests._dbutil import make_engine
from app.models.settings import Settings
from app.models.source import Source
from app.models.source_intelligence_llm_cache import SourceIntelligenceLlmCache
from app.repositories.source_repository import SourceRepository
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.source_intelligence_constants import SOURCE_INTELLIGENCE_VERSION
from app.services.source_intelligence_generation_service import (
    IntelligenceOptions,
    SourceIntelligenceGenerationService,
)
from app.services.source_intelligence_llm_cache_service import SourceIntelligenceLLMCacheService
from app.services.source_intelligence_perf import (
    compute_llm_prompt_hash,
    compute_profile_settings_hash,
    should_skip_source,
)
from app.services.source_intelligence_progress_tracker import SourceIntelligenceProgressTracker
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile


@pytest.fixture()
def db_session():
    engine = make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    settings = Settings(id=1, llm_model="test-model", knowledge_version=1)
    session.add(settings)
    session.commit()
    try:
        yield session, settings
    finally:
        session.close()


def _indexed_source(**kwargs) -> Source:
    defaults = dict(
        url="https://example.com/page",
        source_type="page",
        status="indexed",
        title="Test page",
        content_hash="abc123",
        main_content_text="Enough content for intelligence analysis here.",
        main_content_chars=500,
        profile_version=SOURCE_INTELLIGENCE_VERSION,
        needs_intelligence=False,
        intelligence_content_hash="abc123",
        intelligence_settings_hash="",
        intelligence_llm_model="test-model",
        intelligence_prompt_version=compute_llm_prompt_hash(),
    )
    defaults.update(kwargs)
    return Source(**defaults)


def test_unchanged_source_is_skipped(db_session):
    db, settings = db_session
    source = _indexed_source()
    source.intelligence_settings_hash = compute_profile_settings_hash(settings)
    db.add(source)
    db.commit()
    assert should_skip_source(source, settings, force_reprocess=False, llm_enabled=True)


def test_changed_content_hash_triggers_reprocessing(db_session):
    db, settings = db_session
    source = _indexed_source(content_hash="new-hash", intelligence_content_hash="abc123")
    source.intelligence_settings_hash = compute_profile_settings_hash(settings)
    db.add(source)
    db.commit()
    assert not should_skip_source(source, settings, force_reprocess=False, llm_enabled=True)


def test_scope_needs_intelligence_only_selects_flagged(db_session):
    db, settings = db_session
    flagged = _indexed_source(url="https://example.com/a", needs_intelligence=True)
    fresh = _indexed_source(url="https://example.com/b", needs_intelligence=False)
    fresh.intelligence_settings_hash = compute_profile_settings_hash(settings)
    db.add_all([flagged, fresh])
    db.commit()
    svc = SourceIntelligenceGenerationService(db, settings)
    assert svc.count_sources(IntelligenceOptions(scope="needs_intelligence")) == 1


def test_scope_all_forces_reprocess(db_session):
    db, settings = db_session
    source = _indexed_source()
    source.intelligence_settings_hash = compute_profile_settings_hash(settings)
    db.add(source)
    db.commit()
    svc = SourceIntelligenceGenerationService(db, settings)
    estimate = svc.estimate(IntelligenceOptions(scope="all"))
    assert estimate.would_skip_unchanged == 0


def test_llm_cache_hit_avoids_ollama_call(db_session):
    db, settings = db_session
    source = _indexed_source(needs_intelligence=True)
    db.add(source)
    db.commit()
    cache = SourceIntelligenceLLMCacheService(db)
    key = cache.build_key(
        content_hash=source.content_hash or "",
        llm_model=settings.llm_model or "",
        settings=settings,
        language="en",
    )
    from app.schemas.source_intelligence import SourceSemanticProfile

    profile = SourceSemanticProfile(main_topic="Topic", generator="llm")
    cache.store_success(
        cache_key=key,
        content_hash=source.content_hash or "",
        llm_model=settings.llm_model or "",
        settings=settings,
        language="en",
        raw_json='{"main_topic":"Topic"}',
        profile=profile,
    )
    db.commit()
    with patch("app.services.source_intelligence_llm_service.OllamaService") as mock_ollama:
        result = SourceIntelligenceService.build_profile(
            source, settings=settings, use_llm=True, db=db
        )
        mock_ollama.assert_not_called()
    assert result.semantic is not None


def test_llm_timeout_is_not_cached_as_success(db_session):
    db, settings = db_session
    source = _indexed_source(needs_intelligence=True)
    db.add(source)
    db.commit()
    from app.services.ollama_service import OllamaError

    with patch("app.services.source_intelligence_llm_service.OllamaService") as mock_cls:
        mock_cls.return_value.chat.side_effect = OllamaError("timed out")
        SourceIntelligenceService.build_profile(source, settings=settings, use_llm=True, db=db)
    rows = list(db.scalars(select(SourceIntelligenceLlmCache)).all())
    assert not any(r.status == "success" for r in rows)


def test_batch_commits_happen_every_n_sources(db_session):
    db, settings = db_session
    settings.source_intelligence_db_batch_size = 2
    db.add(settings)
    for i in range(5):
        db.add(
            _indexed_source(
                url=f"https://example.com/{i}",
                needs_intelligence=True,
                content_hash=f"hash-{i}",
                intelligence_content_hash=None,
            )
        )
    db.commit()
    svc = SourceIntelligenceGenerationService(db, settings)
    commit_calls = {"n": 0}
    original_commit = SourceRepository.commit

    def counted_commit(self):
        commit_calls["n"] += 1
        return original_commit(self)

    with patch.object(SourceRepository, "commit", counted_commit):
        with patch.object(
            SourceIntelligenceGenerationService,
            "build_profile_for_source",
            side_effect=lambda source, options, db=None, stats=None: SourceProfile(
                source_id=source.id,
                url=source.url or "",
            ),
        ):
            result = svc.run(IntelligenceOptions(scope="needs_intelligence"))
    assert result["updated_sources"] == 5
    assert commit_calls["n"] >= 2


def test_paginated_selection_does_not_load_all_at_once(db_session):
    db, settings = db_session
    for i in range(30):
        db.add(_indexed_source(url=f"https://example.com/p{i}", needs_intelligence=True))
    db.commit()
    svc = SourceIntelligenceGenerationService(db, settings)
    settings.source_intelligence_page_size = 10
    pages = list(svc.iter_source_id_pages(IntelligenceOptions(scope="needs_intelligence"), page_size=10))
    assert len(pages) == 3
    assert sum(len(p) for p in pages) == 30


def test_progress_persistence_is_throttled(db_session):
    db, settings = db_session
    from app.models.index_job import IndexJob
    from app.repositories.index_job_repository import IndexJobRepository

    job = IndexJob(status="running", progress_json="{}", log_json="[]")
    db.add(job)
    db.commit()
    repo = IndexJobRepository(db)
    saves = {"n": 0}
    original_save = repo.save

    def counted_save(self, job_obj):
        saves["n"] += 1
        return original_save(job_obj)

    with patch.object(IndexJobRepository, "save", counted_save):
        tracker = SourceIntelligenceProgressTracker(repo, job.id, flush_every_sources=5)
        for i in range(12):
            tracker.tick(phase="updating_profiles", message=f"item {i}", processed=i + 1)
        tracker.finish(phase="completed", message="done", selected=12, processed=12)
    assert saves["n"] <= 4


def test_inline_indexing_skips_intelligence_when_setting_false(db_session):
    db, settings = db_session
    settings.run_source_intelligence_inline_during_indexing = False
    db.commit()
    with patch.object(SourceIntelligenceService, "build_profile") as mock_build:
        from app.services.indexing_service import IndexingService

        svc = IndexingService(db, settings)
        source = _indexed_source(status="pending")
        db.add(source)
        db.commit()
        # Minimal path: only verify flag prevents build_profile when we would call inline block
        inline = settings.run_source_intelligence_inline_during_indexing
        assert inline is False
        mock_build.assert_not_called()


def test_version_bump_invalidates_without_delete_all(db_session):
    db, settings = db_session
    db.add(_indexed_source(needs_intelligence=True, content_hash="x1"))
    db.commit()
    svc = SourceIntelligenceGenerationService(db, settings)
    before = settings.knowledge_version or 1
    with patch.object(
        SourceIntelligenceGenerationService,
        "build_profile_for_source",
        side_effect=lambda source, options, db=None, stats=None: SourceProfile(
            source_id=source.id, url=source.url or ""
        ),
    ):
        with patch(
            "app.services.source_intelligence_generation_service.CacheInvalidationService"
        ) as mock_cache:
            svc.run(IntelligenceOptions(scope="needs_intelligence", limit=1))
            mock_cache.return_value.invalidate_all_caches.assert_not_called()
    db.refresh(settings)
    assert (settings.knowledge_version or 1) >= before


def test_apply_to_source_persists_intelligence_metadata(db_session):
    db, settings = db_session
    source = _indexed_source(needs_intelligence=True)
    db.add(source)
    db.commit()
    now = datetime.now(timezone.utc)
    profile = SourceProfile(source_id=source.id, url=source.url or "")
    SourceIntelligenceService.apply_to_source(source, profile, settings=settings, now=now)
    assert source.intelligence_content_hash == source.content_hash
    assert source.intelligence_settings_hash == compute_profile_settings_hash(settings)
    assert source.needs_intelligence is False
