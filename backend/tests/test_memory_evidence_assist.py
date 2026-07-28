"""RFC-100 Step 047 — advisory Memory evidence assist tests."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.settings import Settings
from app.services.cache_namespace_service import build_retrieval_namespace, namespace_hash
from app.services.epistemic_memory.memory_region_types import (
    LIMIT_CORPUS_SCOPE_UNCONFIGURED,
    MemoryClaimView,
    MemoryCorpusScope,
    MemoryEvidenceRef,
    MemoryIsolationScope,
    MemoryRegionRequest,
    MemoryRegionView,
)
from app.services.feature_flags import memory_evidence_assist_enabled
from app.services.rag_service import RagResult, RagSource
from app.services.reasoning.evidence_sufficiency import (
    assess_evidence_sufficiency,
    enrich_assessment_with_memory_assist,
)
from app.services.reasoning.memory_assist_policy import (
    MemoryAssistPolicy,
    corpus_boundary_fingerprint_for_settings,
    memory_assist_effective,
)
from app.services.reasoning.memory_assist_types import (
    SKIP_CACHE_NAMESPACE_V2_REQUIRED,
    SKIP_REASONING_DISABLED,
    MemoryAssistResult,
)
from app.services.reasoning.memory_request_builder import build_memory_region_request
from app.services.reasoning.reasoning_service import ReasoningService
from app.services.reasoning.types import ReasoningRequest
from app.services.retrieval_pipeline_service import PreparedRetrieval, RetrievalDiagnostics
from app.schemas.knowledge_profile import AppliedKnowledgeConfig, KnowledgeProfile
from app.services.retrieval_intent_service import RetrievalIntentResult

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
REASONING_PKG = APP_ROOT / "services" / "reasoning"
MEMORY_ASSIST_FILES = (
    "memory_assist_types.py",
    "memory_assist_policy.py",
    "memory_request_builder.py",
)

FORBIDDEN_IN_ASSIST = frozenset(
    {
        "qdrant",
        "Qdrant",
        "ollama",
        "Ollama",
        "prompt_builder",
        "CompactPromptBuilder",
        "MemoryVersionService.bump",
        "KnowledgeVersionService.bump",
        "TensionSurfacing",
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


def _prepared(**kwargs) -> PreparedRetrieval:
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
    base = PreparedRetrieval(
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
    )
    for k, v in kwargs.items():
        object.__setattr__(base, k, v) if hasattr(base, k) else setattr(base, k, v)
    return base


def _region_view(**kwargs) -> MemoryRegionView:
    request = MemoryRegionRequest(
        isolation=MemoryIsolationScope(corpus_scope=MemoryCorpusScope.DEPLOYMENT),
    )
    defaults = dict(
        request_echo=request,
        matched_claims=(),
        total_matched=0,
        provenance_excluded_count=0,
        excluded_superseded_count=0,
        excluded_scope_mismatch_count=0,
        provenance_summary={},
        page_provenance_summary={},
        limitations=(),
        isolation_scope_echo=request.isolation,
        corpus_scope=MemoryCorpusScope.DEPLOYMENT,
        corpus_hosts=("ukrsibbank.com",),
        corpus_anchor_source_ids=(),
        corpus_anchor_source_count=0,
        corpus_scope_configured=True,
        corpus_scope_complete=True,
        corpus_limitations=(),
    )
    defaults.update(kwargs)
    return MemoryRegionView(**defaults)


@pytest.mark.unit
def test_migration_0016_adds_memory_evidence_assist_flag():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0016_memory_evidence_assist_enabled.py"
    )
    spec = importlib.util.spec_from_file_location("m16", path)
    m16 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m16)
    assert m16.revision == "0016_memory_evidence_assist_enabled"
    assert m16.down_revision == "0015_memory_shadow_write_enabled"


    assert memory_evidence_assist_enabled(Settings()) is False


@pytest.mark.unit
def test_memory_assist_effective_requires_reasoning_and_cache_v2(monkeypatch):
    s = _settings(memory_evidence_assist_enabled=True, cache_namespace_v2_enabled=True)
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    assert memory_assist_effective(s) is True
    get_config.cache_clear()


@pytest.mark.unit
def test_assist_on_reasoning_off_skipped(monkeypatch):
    s = _settings(memory_evidence_assist_enabled=True, cache_namespace_v2_enabled=True)
    monkeypatch.delenv("REASONING_SERVICE_ENABLED", raising=False)
    from app.core.config import get_config

    get_config.cache_clear()
    result = MemoryAssistPolicy(MagicMock()).attempt(_prepared(), s)
    assert result.path == "skipped"
    assert result.skipped_reason == SKIP_REASONING_DISABLED
    get_config.cache_clear()


@pytest.mark.unit
def test_assist_on_cache_v2_off_skipped(monkeypatch):
    s = _settings(memory_evidence_assist_enabled=True, cache_namespace_v2_enabled=False)
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    result = MemoryAssistPolicy(MagicMock()).attempt(_prepared(), s)
    assert result.path == "skipped"
    assert result.skipped_reason == SKIP_CACHE_NAMESPACE_V2_REQUIRED
    get_config.cache_clear()


@pytest.mark.unit
def test_corpus_unconfigured_no_read(monkeypatch):
    s = _settings(
        memory_evidence_assist_enabled=True,
        cache_namespace_v2_enabled=True,
        allowed_domains_json="[]",
        site_url=None,
    )
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    with patch(
        "app.services.reasoning.memory_assist_policy.EpistemicMemoryService"
    ) as svc:
        with patch(
            "app.services.reasoning.memory_assist_policy.MemoryVersionService"
        ) as mvs:
            mvs.return_value.get.return_value = 177
            result = MemoryAssistPolicy(MagicMock()).attempt(_prepared(), s)
        svc.return_value.read_region.assert_not_called()
    assert result.path == "empty"
    assert LIMIT_CORPUS_SCOPE_UNCONFIGURED in result.corpus_limitations
    get_config.cache_clear()


@pytest.mark.unit
def test_request_builder_uses_deployment_corpus():
    req = build_memory_region_request(_prepared())
    isolation = req.normalized_isolation()
    assert isolation.corpus_scope == MemoryCorpusScope.DEPLOYMENT
    assert req.include_evidence is True
    assert req.topic_key == "organization"


@pytest.mark.unit
def test_supported_claim_produces_observation_hints(monkeypatch):
    s = _settings(memory_evidence_assist_enabled=True, cache_namespace_v2_enabled=True)
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    claim = MemoryClaimView(
        claim_id=1,
        proposition="SECRET TEXT",
        attribution="source_intelligence",
        epistemic_status="proposal",
        confidence=None,
        provenance_kind="source_intelligence",
        provenance_ref=None,
        scope=None,
        superseded=False,
        superseded_by_id=None,
        revision_of_id=None,
        evidence=(
            MemoryEvidenceRef(
                evidence_link_id=1,
                observation_ref_id=42,
                role="support",
                provenance_kind="source_intelligence",
                provenance_ref=None,
                source_id=5055,
                chunk_id=1,
                excerpt="ex",
                content_hash="h",
                observed_at=None,
            ),
        ),
        evidence_loaded=True,
        has_support=True,
        has_conflict=False,
        support_observation_source_ids=(5055,),
    )
    view = _region_view(matched_claims=(claim,), total_matched=1)
    with patch(
        "app.services.reasoning.memory_assist_policy.EpistemicMemoryService"
    ) as svc:
        svc.return_value.read_region.return_value = view
        with patch(
            "app.services.reasoning.memory_assist_policy.MemoryVersionService"
        ) as mvs:
            mvs.return_value.get.return_value = 177
            result = MemoryAssistPolicy(MagicMock()).attempt(_prepared(), s)
    assert result.usable_for_evidence is True
    assert 42 in result.observation_ref_ids
    assert 5055 in result.source_ids
    diag = result.to_diagnostics()
    assert "SECRET" not in json.dumps(diag)
    get_config.cache_clear()


@pytest.mark.unit
def test_unsupported_claim_not_usable(monkeypatch):
    s = _settings(memory_evidence_assist_enabled=True, cache_namespace_v2_enabled=True)
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    claim = MemoryClaimView(
        claim_id=2,
        proposition="p",
        attribution="source_intelligence",
        epistemic_status="proposal",
        confidence=None,
        provenance_kind="source_intelligence",
        provenance_ref=None,
        scope=None,
        superseded=False,
        superseded_by_id=None,
        revision_of_id=None,
        evidence=(),
        evidence_loaded=True,
        has_support=False,
        has_conflict=False,
        support_observation_source_ids=(),
    )
    view = _region_view(matched_claims=(claim,), total_matched=1)
    with patch(
        "app.services.reasoning.memory_assist_policy.EpistemicMemoryService"
    ) as svc:
        svc.return_value.read_region.return_value = view
        with patch(
            "app.services.reasoning.memory_assist_policy.MemoryVersionService"
        ) as mvs:
            mvs.return_value.get.return_value = 177
            result = MemoryAssistPolicy(MagicMock()).attempt(_prepared(), s)
    assert result.usable_for_evidence is False
    get_config.cache_clear()


@pytest.mark.unit
def test_memory_exception_fail_open(monkeypatch):
    s = _settings(memory_evidence_assist_enabled=True, cache_namespace_v2_enabled=True)
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    with patch(
        "app.services.reasoning.memory_assist_policy.EpistemicMemoryService"
    ) as svc:
        svc.return_value.read_region.side_effect = RuntimeError("db down")
        with patch(
            "app.services.reasoning.memory_assist_policy.MemoryVersionService"
        ) as mvs:
            mvs.return_value.get.return_value = 177
            result = MemoryAssistPolicy(MagicMock()).attempt(_prepared(), s)
    assert result.path == "failed"
    get_config.cache_clear()


@pytest.mark.unit
def test_empty_memory_does_not_reduce_sufficiency():
    base = assess_evidence_sufficiency(
        RagResult(
            answer="a",
            sources=[
                RagSource(title="t", url="https://site/a", source_type="page", score=0.9)
            ],
            used_context=True,
            query_intent="contacts_query",
        )
    )
    enriched = enrich_assessment_with_memory_assist(
        base, MemoryAssistResult.off()
    )
    assert enriched.evidence_sufficient == base.evidence_sufficient


@pytest.mark.unit
def test_cache_namespace_assist_off_by_default():
    ns = build_retrieval_namespace(_settings())
    assert ns["memory_evidence_assist"] == "off"
    assert "corpus_boundary_fingerprint" not in ns


@pytest.mark.unit
def test_cache_namespace_assist_v1_with_fingerprint(monkeypatch):
    s = _settings(cache_namespace_v2_enabled=True, memory_evidence_assist_enabled=True)
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    fp = corpus_boundary_fingerprint_for_settings(s)
    with patch(
        "app.services.cache_namespace_service.MemoryVersionService"
    ) as mvs:
        mvs.return_value.get.return_value = 177
        ns = build_retrieval_namespace(
            s,
            db=MagicMock(),
            memory_assist_active=True,
            corpus_boundary_fingerprint=fp,
        )
    assert ns["memory_evidence_assist"] == "v1"
    assert ns["corpus_boundary_fingerprint"] == fp
    assert ns["memory_version"] is not None
    get_config.cache_clear()


@pytest.mark.unit
def test_corpus_fingerprint_changes_with_domains():
    s1 = _settings(allowed_domains_json=json.dumps(["ukrsibbank.com"]))
    s2 = _settings(allowed_domains_json=json.dumps(["example.com"]))
    assert corpus_boundary_fingerprint_for_settings(s1) != corpus_boundary_fingerprint_for_settings(
        s2
    )


@pytest.mark.unit
def test_memory_assist_modules_boundary_guards():
    violations: list[str] = []
    for name in MEMORY_ASSIST_FILES:
        path = REASONING_PKG / name
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_IN_ASSIST:
            if token in text:
                violations.append(f"{name}: {token}")
    assert violations == []


@pytest.mark.unit
def test_memory_assist_reads_epistemic_service_not_orm():
    path = REASONING_PKG / "memory_assist_policy.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert "app.services.epistemic_memory.epistemic_memory_service" in imports
    assert not any("app.models.epistemic_memory" in i for i in imports)


@pytest.mark.unit
def test_reasoning_coordinator_invokes_memory_once(monkeypatch):
    s = _settings(memory_evidence_assist_enabled=True, cache_namespace_v2_enabled=True)
    monkeypatch.setenv("REASONING_SERVICE_ENABLED", "true")
    monkeypatch.setenv("EVIDENCE_ASSEMBLY_ENABLED", "true")
    from app.core.config import get_config

    get_config.cache_clear()
    calls = {"assist": 0, "prepare": 0, "assemble": 0}

    def _fake_attempt(self, prepared, settings):
        calls["assist"] += 1
        return MemoryAssistResult.off()

    def _fake_prepare(self, *args, **kwargs):
        calls["prepare"] += 1
        return PreparedRetrieval(
            message="q",
            normalized="q",
            profile=KnowledgeProfile(),
            intent_result=RetrievalIntentResult(intent="x", legacy_intent="unknown"),
            applied_config=AppliedKnowledgeConfig(),
            query_language="uk",
            diagnostics=RetrievalDiagnostics(),
            query_vector=None,
            candidate_count=30,
            t0=0.0,
        )

    def _fake_assemble(self, prepared):
        calls["assemble"] += 1
        from app.services.retrieval_engine.pipeline import DocumentRetrievalResult
        from app.services.retrieval_engine.types import RetrievalQualityMetrics

        return DocumentRetrievalResult(
            selected_hits=[],
            all_documents=[],
            selected_documents=[],
            rejected_documents=[],
            quality_metrics=RetrievalQualityMetrics(),
            pipeline_stages=[],
            chunk_debug={},
        )

    def _fake_finalize(self, prepared, doc_result, **kwargs):
        from app.services.retrieval_pipeline_service import PipelineResult

        return PipelineResult(
            hits=[],
            context=None,
            diagnostics=prepared.diagnostics,
            intent_result=prepared.intent_result,
            applied_config=prepared.applied_config,
            memory_assist=prepared.memory_assist,
        )

    monkeypatch.setattr(MemoryAssistPolicy, "attempt", _fake_attempt)
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
    svc._coordinate_pipeline("q", "q")
    assert calls == {"assist": 1, "prepare": 1, "assemble": 1}
    get_config.cache_clear()
