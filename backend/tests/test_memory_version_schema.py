"""RFC-100 Step 020 — memory_version schema substrate tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import inspect

from app.models.settings import Settings
from app.schemas.settings import SettingsRead
from app.services.cache_namespace_service import build_retrieval_namespace
from app.services.knowledge_version_service import KnowledgeVersionService


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0012_memory_version.py"
)


@pytest.mark.unit
def test_settings_model_memory_version_column_default_is_one():
    columns = {col.key: col for col in inspect(Settings).columns}
    assert "memory_version" in columns
    assert columns["memory_version"].default.arg == 1


@pytest.mark.unit
def test_settings_model_knowledge_version_unchanged():
    columns = {col.key: col for col in inspect(Settings).columns}
    assert "knowledge_version" in columns
    assert columns["knowledge_version"].default.arg == 1


@pytest.mark.unit
def test_settings_read_schema_includes_memory_version():
    payload = SettingsRead.model_validate(
        {
            "id": 1,
            "knowledge_version": 2,
            "memory_version": 1,
            "site_url": None,
            "sitemap_url": None,
            "crawl_depth": 2,
            "allowed_domains": [],
            "deny_url_patterns": [],
            "allowed_file_types": ["pdf"],
            "scan_mode": "pages_only",
            "enable_file_indexing": False,
            "scan_all_pages": False,
            "scan_all_files": False,
            "llm_model": "test",
            "embedding_model": "test",
            "qdrant_collection": "test",
            "chunk_size": 800,
            "chunk_overlap": 120,
            "top_k": 5,
            "similarity_threshold": 0.55,
            "temperature": 0.1,
            "max_tokens": 1024,
            "system_prompt": "",
            "fallback_answer": "fallback",
            "enable_sources": True,
            "enable_chat_logs": True,
            "request_timeout_seconds": 30,
            "max_pages_per_run": 200,
            "max_files_per_run": 100,
            "indexed_page_refresh_interval_hours": 168,
            "indexed_file_refresh_interval_hours": 168,
            "default_response_language": "uk",
            "dashboard_language": "uk",
            "enable_source_links": True,
            "enable_reranking": True,
            "enable_ukrainian_polish_pass": False,
            "fast_mode_enabled": False,
            "enable_retrieval_cache": True,
            "enable_semantic_answer_cache": True,
            "retrieval_cache_ttl_seconds": 3600,
            "answer_cache_ttl_seconds": 86400,
            "semantic_cache_similarity_threshold": 0.93,
            "max_cached_answers": 5000,
            "retrieval_mode": "hybrid",
            "enable_query_expansion": True,
            "enable_retrieval_debug": False,
            "enable_intent_aware_retrieval": True,
            "enable_canonical_source_selection": True,
            "enable_news_deprioritization_for_overview_queries": True,
            "fallback_second_pass_enabled": True,
            "enable_broad_question_mode": True,
            "enable_context_builder": True,
            "retrieval_candidate_count": 30,
            "max_pages_in_context": 3,
            "max_chunks_per_page": 2,
            "enable_tracing": True,
            "enable_trace_storage": True,
            "enable_request_metadata_logging": True,
            "enable_chat_debug_payload": True,
            "enable_semantic_diagnostics_v2": False,
            "max_trace_retention_days": 30,
            "max_concurrent_chat_requests": 20,
            "max_concurrent_llm_requests": 2,
            "max_concurrent_embedding_requests": 2,
            "max_concurrent_background_embedding_requests": 1,
            "chat_total_timeout_seconds": 120,
            "ollama_generation_timeout_seconds": 60,
            "ollama_embedding_timeout_seconds": 30,
            "qdrant_timeout_seconds": 30,
        }
    )
    assert payload.memory_version == 1
    assert payload.knowledge_version == 2


@pytest.mark.unit
def test_settings_read_backward_compatible_without_memory_version_key():
    """Legacy API payloads without memory_version still validate when omitted on read model."""
    minimal = SettingsRead.model_validate(
        {
            "id": 1,
            "knowledge_version": 3,
            "site_url": None,
            "sitemap_url": None,
            "crawl_depth": 2,
            "allowed_domains": [],
            "deny_url_patterns": [],
            "allowed_file_types": ["pdf"],
            "scan_mode": "pages_only",
            "enable_file_indexing": False,
            "scan_all_pages": False,
            "scan_all_files": False,
            "llm_model": "test",
            "embedding_model": "test",
            "qdrant_collection": "test",
            "chunk_size": 800,
            "chunk_overlap": 120,
            "top_k": 5,
            "similarity_threshold": 0.55,
            "temperature": 0.1,
            "max_tokens": 1024,
            "system_prompt": "",
            "fallback_answer": "fallback",
            "enable_sources": True,
            "enable_chat_logs": True,
            "request_timeout_seconds": 30,
            "max_pages_per_run": 200,
            "max_files_per_run": 100,
            "indexed_page_refresh_interval_hours": 168,
            "indexed_file_refresh_interval_hours": 168,
            "default_response_language": "uk",
            "dashboard_language": "uk",
            "enable_source_links": True,
            "enable_reranking": True,
            "enable_ukrainian_polish_pass": False,
            "fast_mode_enabled": False,
            "enable_retrieval_cache": True,
            "enable_semantic_answer_cache": True,
            "retrieval_cache_ttl_seconds": 3600,
            "answer_cache_ttl_seconds": 86400,
            "semantic_cache_similarity_threshold": 0.93,
            "max_cached_answers": 5000,
            "retrieval_mode": "hybrid",
            "enable_query_expansion": True,
            "enable_retrieval_debug": False,
            "enable_intent_aware_retrieval": True,
            "enable_canonical_source_selection": True,
            "enable_news_deprioritization_for_overview_queries": True,
            "fallback_second_pass_enabled": True,
            "enable_broad_question_mode": True,
            "enable_context_builder": True,
            "retrieval_candidate_count": 30,
            "max_pages_in_context": 3,
            "max_chunks_per_page": 2,
            "enable_tracing": True,
            "enable_trace_storage": True,
            "enable_request_metadata_logging": True,
            "enable_chat_debug_payload": True,
            "enable_semantic_diagnostics_v2": False,
            "max_trace_retention_days": 30,
            "max_concurrent_chat_requests": 20,
            "max_concurrent_llm_requests": 2,
            "max_concurrent_embedding_requests": 2,
            "max_concurrent_background_embedding_requests": 1,
            "chat_total_timeout_seconds": 120,
            "ollama_generation_timeout_seconds": 60,
            "ollama_embedding_timeout_seconds": 30,
            "qdrant_timeout_seconds": 30,
        }
    )
    assert minimal.memory_version is None


@pytest.mark.unit
def test_settings_read_includes_memory_version_field():
    assert "memory_version" in SettingsRead.model_fields


@pytest.mark.unit
def test_settings_update_does_not_expose_memory_version():
    from app.schemas.settings import SettingsUpdate

    assert "memory_version" not in SettingsUpdate.model_fields
    assert "knowledge_version" not in SettingsUpdate.model_fields


@pytest.mark.unit
def test_existing_settings_load_preserves_knowledge_version_and_memory_default():
    """Simulates a post-migration row: knowledge_version intact, memory_version=1."""
    settings = Settings(knowledge_version=5, memory_version=1)
    assert settings.knowledge_version == 5
    assert settings.memory_version == 1


@pytest.mark.unit
def test_migration_0012_is_additive_with_default_one():
    spec = importlib.util.spec_from_file_location("migration_0012", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "0012_memory_version"
    assert module.down_revision == "0011_semantic_diagnostics_v2"
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "memory_version" in source
    assert 'server_default="1"' in source or "server_default=1" in source


@pytest.mark.unit
def test_cache_namespace_still_uses_knowledge_version_only():
    settings = Settings(knowledge_version=7, memory_version=99)
    namespace = build_retrieval_namespace(settings)
    assert namespace["index_version"] == "7"
    assert "memory_version" not in namespace


@pytest.mark.unit
def test_knowledge_version_service_unchanged(monkeypatch):
    class _FakeRepo:
        def get_or_create(self):
            return Settings(knowledge_version=5, memory_version=1)

    monkeypatch.setattr(
        "app.services.knowledge_version_service.SettingsRepository",
        lambda db: _FakeRepo(),
    )
    assert KnowledgeVersionService(db=None).get() == 5
