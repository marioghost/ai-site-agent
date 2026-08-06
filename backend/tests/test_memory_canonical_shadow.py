"""RFC-100 Step 048 — Memory canonical shadow comparator tests."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.settings import Settings
from app.services.feature_flags import (
    memory_canonical_shadow_effective,
    memory_canonical_shadow_enabled,
)
from app.services.qdrant_service import SearchHit
from app.services.reasoning.evidence_sufficiency import build_reasoning_diagnostics
from app.services.reasoning.evidence_sufficiency import assess_evidence_sufficiency
from app.services.reasoning.memory_assist_types import MemoryAssistResult
from app.services.reasoning.memory_canonical_shadow_comparator import (
    MemoryCanonicalShadowComparator,
)
from app.services.reasoning.memory_canonical_shadow_types import (
    ALL_SHADOW_DIVERGENCE_CODES,
    DIVERGENCE_CANONICAL_ALIGNED,
    DIVERGENCE_MEMORY_EMPTY,
    DIVERGENCE_MEMORY_SPARSE,
    DIVERGENCE_NO_OVERLAP,
    DIVERGENCE_PARTIAL_OVERLAP,
    DIVERGENCE_RETRIEVAL_SOURCE_NOT_IN_MEMORY,
    MemoryCanonicalShadowInput,
    SHADOW_SKIP_FLAG_OFF,
    SHADOW_SKIP_MEMORY_ASSIST_REQUIRED,
)
from app.services.reasoning.reasoning_service import ReasoningService
from app.services.rag_service import RagResult, RagSource
from app.services.retrieval_engine.pipeline import DocumentRetrievalResult
from app.services.retrieval_engine.types import RetrievalQualityMetrics
from app.services.retrieval_intent_service import RetrievalIntentResult
from app.services.retrieval_pipeline_service import (
    PipelineResult,
    PreparedRetrieval,
    RetrievalDiagnostics,
)
from app.schemas.knowledge_profile import AppliedKnowledgeConfig, KnowledgeProfile
from tests._rag_planning_helpers import planner_decision_for_test

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
REASONING_PKG = APP_ROOT / "services" / "reasoning"
SHADOW_FILES = (
    "memory_canonical_shadow_types.py",
    "memory_canonical_shadow_comparator.py",
    "memory_canonical_shadow_input_builder.py",
)

FORBIDDEN_IN_SHADOW = frozenset(
    {
        "qdrant",
        "Qdrant",
        "read_region",
        "EpistemicMemoryService",
        "DocumentFirstRetrievalPipeline",
        "EvidenceAssemblyService",
        "ollama",
        "Ollama",
        "prompt_builder",
        "CompactPromptBuilder",
        "fastapi",
    }
)


def _settings(**kwargs) -> Settings:
    base = Settings(
        knowledge_version=1,
        memory_version=10,
        embedding_model="bge-m3",
        qdrant_collection="site",
        llm_model="test",
        allowed_domains_json=json.dumps(["ukrsibbank.com"]),
    )
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def _hit(source_id: int, *, document_type: str = "about_page", hint: str = "about") -> SearchHit:
    return SearchHit(
        score=0.9,
        source_id=source_id,
        chunk_index=0,
        title=f"Page {source_id}",
        url=f"https://site/page/{source_id}",
        source_type="page",
        text="content",
        document_type=document_type,
        content_type_hint=hint,
    )


def _assist(**kwargs) -> MemoryAssistResult:
    base = MemoryAssistResult(
        attempted=True,
        path="used",
        region_found=True,
        matched_claim_count=2,
        supported_claim_count=1,
        conflicted_claim_count=0,
        source_ids=(1, 2),
        support_source_ids=(2,),
        observation_ref_ids=(101,),
        support_observation_ref_ids=(101,),
        topic_hints=("organization",),
        page_role_hints=("about",),
        limitations=(),
        corpus_limitations=(),
        corpus_scope_configured=True,
        corpus_scope_complete=False,
        completeness_unknown=True,
        usable_for_evidence=True,
        memory_version=10,
    )
    for k, v in kwargs.items():
        object.__setattr__(base, k, v)
    return base


def _prepared(memory_assist: MemoryAssistResult | None = None) -> PreparedRetrieval:
    intent = RetrievalIntentResult(
        intent="about",
        legacy_intent="entity_overview",
        answer_strategy="generic",
        confidence=0.9,
    )
    applied = AppliedKnowledgeConfig(
        detected_intent="entity_overview",
        matched_topic_key="organization",
        boosted_content_hints=["about"],
        boosted_document_types=["about_page"],
    )
    return PreparedRetrieval(
        message="What is the bank?",
        normalized="what is the bank",
        profile=KnowledgeProfile(),
        intent_result=intent,
        applied_config=applied,
        query_language="uk",
        diagnostics=RetrievalDiagnostics(),
        query_vector=None,
        candidate_count=30,
        t0=0.0,
        memory_assist=memory_assist,
        planner_decision=planner_decision_for_test(
            "What is the bank?",
            intent="entity_overview",
            query_language="uk",
        ),
    )


def _doc_result(*hits: SearchHit) -> DocumentRetrievalResult:
    return DocumentRetrievalResult(
        selected_hits=list(hits),
        all_documents=[],
        selected_documents=[],
        rejected_documents=[],
        quality_metrics=RetrievalQualityMetrics(),
    )


def _pipe_result(*hits: SearchHit) -> PipelineResult:
    prepared = _prepared()
    return PipelineResult(
        hits=list(hits),
        context=None,
        diagnostics=prepared.diagnostics,
        intent_result=prepared.intent_result,
        applied_config=prepared.applied_config,
    )


@pytest.mark.unit
def test_migration_0017_chain():
    m17 = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0017_memory_canonical_shadow_enabled.py"
    )
    assert m17.is_file()
    text = m17.read_text(encoding="utf-8")
    assert 'revision = "0017_memory_canonical_shadow_enabled"' in text
    assert 'down_revision = "0016_memory_evidence_assist_enabled"' in text


@pytest.mark.unit
def test_shadow_flag_defaults_follow_orm_materialization():
    # Unset ORM instance → helper False; explicit True → ON (DB default via migration).
    assert memory_canonical_shadow_enabled(Settings()) is False
    assert memory_canonical_shadow_enabled(
        Settings(memory_canonical_shadow_enabled=True)
    ) is True


@pytest.mark.unit
def test_shadow_effective_requires_all_prerequisites(monkeypatch):
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    s = _settings(
        memory_canonical_shadow_enabled=True,
        memory_evidence_assist_enabled=True,
        cache_namespace_v2_enabled=True,
    )
    assert memory_canonical_shadow_effective(s) is True
    assert memory_canonical_shadow_effective(_settings(memory_canonical_shadow_enabled=False)) is False
    assert memory_canonical_shadow_effective(
        _settings(
            memory_canonical_shadow_enabled=True,
            memory_evidence_assist_enabled=False,
            cache_namespace_v2_enabled=True,
        )
    ) is False
    get_config.cache_clear()


@pytest.mark.unit
def test_comparator_off_when_flag_disabled():
    s = _settings(memory_canonical_shadow_enabled=False)
    result = MemoryCanonicalShadowComparator().compare_pipeline(
        s,
        _assist(),
        _prepared(),
        _doc_result(_hit(1)),
        _pipe_result(_hit(1)),
    )
    assert result.path == "off"
    assert result.skipped_reason == SHADOW_SKIP_FLAG_OFF


@pytest.mark.unit
def test_comparator_skipped_without_assist(monkeypatch):
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    s = _settings(
        memory_canonical_shadow_enabled=True,
        memory_evidence_assist_enabled=False,
        cache_namespace_v2_enabled=True,
    )
    result = MemoryCanonicalShadowComparator().compare_pipeline(
        s,
        MemoryAssistResult.off(),
        _prepared(),
        _doc_result(),
        _pipe_result(),
    )
    assert result.path == "skipped"
    assert result.skipped_reason == SHADOW_SKIP_MEMORY_ASSIST_REQUIRED
    get_config.cache_clear()


@pytest.mark.unit
def test_comparator_aligned_overlap(monkeypatch):
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    s = _settings(
        memory_canonical_shadow_enabled=True,
        memory_evidence_assist_enabled=True,
        cache_namespace_v2_enabled=True,
    )
    assist = _assist(source_ids=(1, 2))
    result = MemoryCanonicalShadowComparator().compare_pipeline(
        s,
        assist,
        _prepared(assist),
        _doc_result(_hit(1), _hit(2)),
        _pipe_result(_hit(1), _hit(2), _hit(3)),
    )
    assert result.path == "compared"
    assert result.canonical_alignment == "aligned"
    assert DIVERGENCE_CANONICAL_ALIGNED in result.divergence_codes
    assert DIVERGENCE_RETRIEVAL_SOURCE_NOT_IN_MEMORY in result.divergence_codes
    assert 3 in result.retrieval_only_source_ids
    get_config.cache_clear()


@pytest.mark.unit
def test_comparator_partial_overlap():
    comp = MemoryCanonicalShadowComparator()
    inp = MemoryCanonicalShadowInput(
        memory_anchor_source_ids=(1, 2),
        support_source_ids=(1, 2),
        support_observation_ref_ids=(10,),
        dfp_selected_source_ids=(1,),
        context_source_ids=(2, 3),
        topic_hints=("organization",),
        page_role_hints=("about",),
        selected_document_types=frozenset({"about_page"}),
        selected_page_roles=frozenset({"about"}),
        matched_topic_key="organization",
        query_intent="entity_overview",
        answer_strategy="generic",
        broad_injected=False,
        canonical_selection_enabled=True,
        memory_assist_path="used",
        memory_assist_usable=True,
        memory_sparse=False,
        memory_empty=False,
        corpus_unconfigured=False,
    )
    result = comp._compare(inp, memory_version=10, started=0.0)
    assert result.canonical_alignment == "partial"
    assert DIVERGENCE_PARTIAL_OVERLAP in result.divergence_codes


@pytest.mark.unit
def test_comparator_no_overlap():
    comp = MemoryCanonicalShadowComparator()
    inp = MemoryCanonicalShadowInput(
        memory_anchor_source_ids=(1,),
        support_source_ids=(1,),
        support_observation_ref_ids=(),
        dfp_selected_source_ids=(5,),
        context_source_ids=(9,),
        topic_hints=(),
        page_role_hints=(),
        selected_document_types=frozenset(),
        selected_page_roles=frozenset(),
        matched_topic_key=None,
        query_intent=None,
        answer_strategy=None,
        broad_injected=False,
        canonical_selection_enabled=True,
        memory_assist_path="used",
        memory_assist_usable=True,
        memory_sparse=False,
        memory_empty=False,
        corpus_unconfigured=False,
    )
    result = comp._compare(inp, memory_version=10, started=0.0)
    assert result.canonical_alignment == "divergent"
    assert DIVERGENCE_NO_OVERLAP in result.divergence_codes


@pytest.mark.unit
def test_comparator_empty_memory_path():
    comp = MemoryCanonicalShadowComparator()
    inp = MemoryCanonicalShadowInput(
        memory_anchor_source_ids=(),
        support_source_ids=(),
        support_observation_ref_ids=(),
        dfp_selected_source_ids=(),
        context_source_ids=(1,),
        topic_hints=(),
        page_role_hints=(),
        selected_document_types=frozenset(),
        selected_page_roles=frozenset(),
        matched_topic_key=None,
        query_intent=None,
        answer_strategy=None,
        broad_injected=False,
        canonical_selection_enabled=True,
        memory_assist_path="empty",
        memory_assist_usable=False,
        memory_sparse=False,
        memory_empty=True,
        corpus_unconfigured=False,
    )
    result = comp._compare(inp, memory_version=10, started=0.0)
    assert result.path == "empty_memory"
    assert DIVERGENCE_MEMORY_EMPTY in result.divergence_codes


@pytest.mark.unit
def test_comparator_sparse_adds_code():
    comp = MemoryCanonicalShadowComparator()
    inp = MemoryCanonicalShadowInput(
        memory_anchor_source_ids=(1,),
        support_source_ids=(1,),
        support_observation_ref_ids=(1,),
        dfp_selected_source_ids=(1,),
        context_source_ids=(1,),
        topic_hints=(),
        page_role_hints=(),
        selected_document_types=frozenset(),
        selected_page_roles=frozenset(),
        matched_topic_key=None,
        query_intent=None,
        answer_strategy=None,
        broad_injected=False,
        canonical_selection_enabled=True,
        memory_assist_path="sparse",
        memory_assist_usable=True,
        memory_sparse=True,
        memory_empty=False,
        corpus_unconfigured=False,
    )
    result = comp._compare(inp, memory_version=10, started=0.0)
    assert DIVERGENCE_MEMORY_SPARSE in result.divergence_codes


@pytest.mark.unit
def test_diagnostics_bounded_no_text():
    assist = _assist()
    comp = MemoryCanonicalShadowComparator()
    inp = MemoryCanonicalShadowInput(
        memory_anchor_source_ids=(1, 2),
        support_source_ids=(1, 2),
        support_observation_ref_ids=(99,),
        dfp_selected_source_ids=(1,),
        context_source_ids=(1, 2),
        topic_hints=("organization",),
        page_role_hints=("about",),
        selected_document_types=frozenset({"about_page"}),
        selected_page_roles=frozenset({"about"}),
        matched_topic_key="organization",
        query_intent="entity_overview",
        answer_strategy="generic",
        broad_injected=False,
        canonical_selection_enabled=True,
        memory_assist_path="used",
        memory_assist_usable=True,
        memory_sparse=False,
        memory_empty=False,
        corpus_unconfigured=False,
    )
    shadow = comp._compare(inp, memory_version=10, started=0.0)
    diag = shadow.to_diagnostics()
    blob = json.dumps(diag)
    for forbidden in ("proposition", "chunk text", "prompt", "answer", "http://", "https://"):
        assert forbidden not in blob.lower()
    assert all(isinstance(c, str) for c in diag["divergence_codes"])
    assert all(c in ALL_SHADOW_DIVERGENCE_CODES for c in diag["divergence_codes"])


@pytest.mark.unit
def test_build_reasoning_diagnostics_includes_shadow():
    stub = RagResult(
        answer="test",
        sources=[RagSource(title="t", url="https://x", source_type="page", score=1.0)],
        used_context=True,
    )
    assessment = assess_evidence_sufficiency(stub)
    assist = _assist()
    comp = MemoryCanonicalShadowComparator()
    shadow = comp._compare(
        MemoryCanonicalShadowInput(
            memory_anchor_source_ids=(1,),
            support_source_ids=(1,),
            support_observation_ref_ids=(),
            dfp_selected_source_ids=(1,),
            context_source_ids=(1,),
            topic_hints=(),
            page_role_hints=(),
            selected_document_types=frozenset(),
            selected_page_roles=frozenset(),
            matched_topic_key=None,
            query_intent=None,
            answer_strategy=None,
            broad_injected=False,
            canonical_selection_enabled=True,
            memory_assist_path="used",
            memory_assist_usable=True,
            memory_sparse=False,
            memory_empty=False,
            corpus_unconfigured=False,
        ),
        memory_version=10,
        started=0.0,
    )
    diag = build_reasoning_diagnostics(
        assessment,
        reasoning_path="reasoning_service",
        memory_assist=assist,
        canonical_shadow=shadow,
    )
    assert "memory_assist" in diag
    assert "memory_canonical_shadow" in diag


@pytest.mark.unit
def test_shadow_modules_boundary_guards():
    violations: list[str] = []
    for name in SHADOW_FILES:
        path = REASONING_PKG / name
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_IN_SHADOW:
            if token in text:
                violations.append(f"{name}: {token}")
    assert violations == []


@pytest.mark.unit
def test_comparator_never_calls_memory_or_retrieval(monkeypatch):
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    s = _settings(
        memory_canonical_shadow_enabled=True,
        memory_evidence_assist_enabled=True,
        cache_namespace_v2_enabled=True,
    )
    with patch(
        "app.services.reasoning.memory_canonical_shadow_comparator.build_memory_canonical_shadow_input"
    ) as build_mock:
        build_mock.side_effect = AssertionError("should use prebuilt input only via builder once")
        assist = _assist()
        MemoryCanonicalShadowComparator().compare_pipeline(
            s,
            assist,
            _prepared(assist),
            _doc_result(_hit(1)),
            _pipe_result(_hit(1)),
        )
        assert build_mock.call_count == 1
    get_config.cache_clear()


@pytest.mark.unit
def test_coordinator_runs_comparator_without_extra_assist(monkeypatch):
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    monkeypatch.setenv("EVIDENCE_ASSEMBLY_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    s = _settings(
        memory_canonical_shadow_enabled=True,
        memory_evidence_assist_enabled=True,
        cache_namespace_v2_enabled=True,
    )
    calls = {"assist": 0, "shadow": 0}

    def _fake_attempt(self, prepared, settings):
        calls["assist"] += 1
        return _assist()

    def _fake_compare(self, settings, memory_assist, prepared, doc_result, pipe_result):
        calls["shadow"] += 1
        from app.services.reasoning.memory_canonical_shadow_types import (
            MemoryCanonicalShadowResult,
        )

        return MemoryCanonicalShadowResult.off()

    def _fake_prepare(self, *args, **kwargs):
        return _prepared()

    def _fake_assemble(self, prepared):
        return _doc_result(_hit(1))

    def _fake_finalize(self, prepared, doc_result, **kwargs):
        return _pipe_result(_hit(1))

    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.MemoryAssistPolicy.attempt",
        _fake_attempt,
    )
    monkeypatch.setattr(
        MemoryCanonicalShadowComparator,
        "compare_pipeline",
        _fake_compare,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RetrievalPipelineService.prepare_query",
        _fake_prepare,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RetrievalPipelineService.assemble_evidence",
        _fake_assemble,
    )
    monkeypatch.setattr(
        "app.services.reasoning.reasoning_service.RetrievalPipelineService.finalize_pipeline",
        _fake_finalize,
    )
    svc = ReasoningService(MagicMock(), s)
    result = svc._coordinate_pipeline("q", "q")
    assert calls == {"assist": 1, "shadow": 1}
    assert result.canonical_shadow is not None
    get_config.cache_clear()


@pytest.mark.unit
def test_shadow_input_uses_support_source_ids_not_anchor():
    assist = _assist(source_ids=(1, 2, 3), support_source_ids=(2,), support_observation_ref_ids=(101,))
    from app.services.reasoning.memory_canonical_shadow_input_builder import (
        build_memory_canonical_shadow_input,
    )

    inp = build_memory_canonical_shadow_input(
        memory_assist=assist,
        prepared=_prepared(assist),
        doc_result=_doc_result(_hit(1)),
        pipe_result=_pipe_result(_hit(1)),
        settings=_settings(),
    )
    assert inp.memory_anchor_source_ids == (1, 2, 3)
    assert inp.support_source_ids == (2,)
    assert inp.support_observation_ref_ids == (101,)


@pytest.mark.unit
def test_pipeline_result_with_canonical_shadow():
    base = _pipe_result(_hit(1))
    shadow = MemoryCanonicalShadowComparator()._compare(
        MemoryCanonicalShadowInput(
            memory_anchor_source_ids=(1,),
            support_source_ids=(1,),
            support_observation_ref_ids=(),
            dfp_selected_source_ids=(1,),
            context_source_ids=(1,),
            topic_hints=(),
            page_role_hints=(),
            selected_document_types=frozenset(),
            selected_page_roles=frozenset(),
            matched_topic_key=None,
            query_intent=None,
            answer_strategy=None,
            broad_injected=False,
            canonical_selection_enabled=True,
            memory_assist_path="used",
            memory_assist_usable=True,
            memory_sparse=False,
            memory_empty=False,
            corpus_unconfigured=False,
        ),
        memory_version=10,
        started=0.0,
    )
    updated = base.with_canonical_shadow(shadow)
    assert updated.canonical_shadow is shadow
    assert base.canonical_shadow is None
