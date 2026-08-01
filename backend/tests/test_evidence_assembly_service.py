"""RFC-100 Step 040 — EvidenceAssemblyService DFP-wrap seam tests."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.evidence_assembly import (
    EVIDENCE_ASSEMBLY_PATH_LEGACY,
    EVIDENCE_ASSEMBLY_PATH_SERVICE,
    EvidenceAssemblyRequest,
    EvidenceAssemblyService,
)
from app.services.qdrant_service import SearchHit
from app.services.retrieval_engine.pipeline import DocumentRetrievalResult
from app.services.retrieval_engine.types import RankedDocument, RetrievalQualityMetrics
from app.services.retrieval_intent_service import RetrievalIntentResult
from app.services.retrieval_pipeline_service import RetrievalPipelineService

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
EA_PKG = APP_ROOT / "services" / "evidence_assembly"


def _intent() -> RetrievalIntentResult:
    return RetrievalIntentResult(
        intent="general_information",
        legacy_intent="unknown",
    )


def _profile() -> KnowledgeProfile:
    return KnowledgeProfile()


def _hit(url: str = "https://site/about", score: float = 0.9) -> SearchHit:
    return SearchHit(
        score=score,
        source_id=10,
        chunk_index=0,
        title="About",
        url=url,
        source_type="page",
        text="About the org",
    )


def _doc(hit: SearchHit | None = None) -> RankedDocument:
    h = hit or _hit()
    return RankedDocument(
        source_id=h.source_id,
        url=h.url,
        title=h.title or "About",
        document_type="generic_page",
        representative_chunk=h,
    )


def _dfp_result(**overrides) -> DocumentRetrievalResult:
    hit = _hit()
    selected = _doc(hit)
    quality = RetrievalQualityMetrics(
        chunks_retrieved=1,
        documents_found=1,
        documents_after_deduplication=1,
        documents_after_reranking=1,
        documents_sent_to_llm=1,
    )
    base = DocumentRetrievalResult(
        selected_hits=[hit],
        all_documents=[selected],
        selected_documents=[selected],
        rejected_documents=[],
        quality_metrics=quality,
        pipeline_stages=[{"stage": "chunk_retrieval", "status": "completed"}],
        chunk_debug={"match_query": "about"},
        retrieval_ms=12,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _request() -> EvidenceAssemblyRequest:
    return EvidenceAssemblyRequest(
        query="What is the org?",
        normalized="what is the org",
        intent_result=_intent(),
        profile=_profile(),
        query_vector=[0.1, 0.2],
        expansion_terms=None,
        query_language="en",
    )


@pytest.mark.unit
def test_evidence_assembly_enabled_defaults_true(monkeypatch):
    from app.core.config import get_config

    monkeypatch.delenv("EVIDENCE_ASSEMBLY_ENABLED", raising=False)
    get_config.cache_clear()
    from app.services.feature_flags import evidence_assembly_enabled

    assert evidence_assembly_enabled() is True
    get_config.cache_clear()


@pytest.mark.unit
def test_evidence_assembly_enabled_reads_env(monkeypatch):
    from app.core.config import get_config

    monkeypatch.setenv("EVIDENCE_ASSEMBLY_ENABLED", "true")
    get_config.cache_clear()
    from app.services.feature_flags import evidence_assembly_enabled

    assert evidence_assembly_enabled() is True
    get_config.cache_clear()


@pytest.mark.unit
def test_evidence_assembly_enabled_kill_switch_false(monkeypatch):
    from app.core.config import get_config

    monkeypatch.setenv("EVIDENCE_ASSEMBLY_ENABLED", "false")
    get_config.cache_clear()
    from app.services.feature_flags import evidence_assembly_enabled

    assert evidence_assembly_enabled() is False
    get_config.cache_clear()


@pytest.mark.unit
def test_evidence_assembly_is_stateless(monkeypatch):
    calls: list[EvidenceAssemblyRequest] = []
    expected = _dfp_result()

    class _FakeDFP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, **kwargs):
            calls.append(kwargs)
            return expected

    monkeypatch.setattr(
        "app.services.evidence_assembly.evidence_assembly_service.DocumentFirstRetrievalPipeline",
        _FakeDFP,
    )
    svc = EvidenceAssemblyService(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    r1 = svc.assemble(_request())
    r2 = svc.assemble(
        EvidenceAssemblyRequest(
            query="Other?",
            normalized="other",
            intent_result=_intent(),
            profile=_profile(),
        )
    )
    assert r1.selected_hits is expected.selected_hits
    assert len(calls) == 2
    assert calls[0]["query"] == "What is the org?"
    assert calls[1]["query"] == "Other?"
    assert not hasattr(svc, "_last_result")
    assert r1 is not r2 or r1.selected_hits == r2.selected_hits


@pytest.mark.unit
def test_evidence_assembly_delegates_to_dfp_exactly_once(monkeypatch):
    run_count = {"n": 0}
    expected = _dfp_result()

    class _FakeDFP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, **kwargs):
            run_count["n"] += 1
            return expected

    monkeypatch.setattr(
        "app.services.evidence_assembly.evidence_assembly_service.DocumentFirstRetrievalPipeline",
        _FakeDFP,
    )
    svc = EvidenceAssemblyService(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    result = svc.assemble(_request())
    assert run_count["n"] == 1
    assert result.selected_hits == expected.selected_hits
    assert result.selected_documents == expected.selected_documents
    assert result.pipeline_stages == expected.pipeline_stages
    assert result.quality_metrics == expected.quality_metrics
    assert result.evidence_assembly_path == EVIDENCE_ASSEMBLY_PATH_SERVICE


@pytest.mark.unit
def test_flag_off_calls_dfp_directly_without_ea(monkeypatch):
    from app.core.config import get_config
    from app.models.settings import Settings

    monkeypatch.setenv("EVIDENCE_ASSEMBLY_ENABLED", "false")
    get_config.cache_clear()

    expected = _dfp_result()
    dfp_runs = {"n": 0}
    ea_inits = {"n": 0}

    class _FakeDFP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, **kwargs):
            dfp_runs["n"] += 1
            return expected

    class _BoomEA:
        def __init__(self, *args, **kwargs) -> None:
            ea_inits["n"] += 1
            raise AssertionError("EvidenceAssemblyService must not be constructed when flag OFF")

        def assemble(self, request):
            raise AssertionError("unreachable")

    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.DocumentFirstRetrievalPipeline",
        _FakeDFP,
    )
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.EvidenceAssemblyService",
        _BoomEA,
    )
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: False,
    )

    settings = Settings(
        top_k=5,
        enable_intent_aware_retrieval=False,
        enable_query_expansion=False,
        enable_broad_question_mode=False,
        enable_canonical_source_selection=False,
        enable_context_builder=False,
    )
    pipeline = RetrievalPipelineService(MagicMock(), settings, MagicMock(), MagicMock())
    result = pipeline.run("What is the org?", "what is the org")

    assert dfp_runs["n"] == 1
    assert ea_inits["n"] == 0
    assert result.diagnostics.evidence_assembly_path == EVIDENCE_ASSEMBLY_PATH_LEGACY
    assert result.hits[0].url == expected.selected_hits[0].url
    get_config.cache_clear()


@pytest.mark.unit
def test_flag_on_routes_through_evidence_assembly_once(monkeypatch):
    from app.models.settings import Settings

    expected = _dfp_result()
    dfp_runs = {"n": 0}
    ea_assemble = {"n": 0}

    class _FakeDFP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, **kwargs):
            dfp_runs["n"] += 1
            return expected

    real_ea = EvidenceAssemblyService

    class _CountingEA(real_ea):
        def assemble(self, request):
            ea_assemble["n"] += 1
            return super().assemble(request)

    monkeypatch.setattr(
        "app.services.evidence_assembly.evidence_assembly_service.DocumentFirstRetrievalPipeline",
        _FakeDFP,
    )
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.EvidenceAssemblyService",
        _CountingEA,
    )
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: True,
    )
    # Flag ON must not construct DFP at RPS layer.
    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.DocumentFirstRetrievalPipeline",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("RPS must not construct DFP directly when EA flag ON")
        ),
    )

    settings = Settings(
        top_k=5,
        enable_intent_aware_retrieval=False,
        enable_query_expansion=False,
        enable_broad_question_mode=False,
        enable_canonical_source_selection=False,
        enable_context_builder=False,
    )
    pipeline = RetrievalPipelineService(MagicMock(), settings, MagicMock(), MagicMock())
    result = pipeline.run("What is the org?", "what is the org")

    assert ea_assemble["n"] == 1
    assert dfp_runs["n"] == 1
    assert result.diagnostics.evidence_assembly_path == EVIDENCE_ASSEMBLY_PATH_SERVICE
    assert [h.url for h in result.hits] == [h.url for h in expected.selected_hits]


@pytest.mark.unit
def test_flag_on_off_structurally_equivalent_retrieval(monkeypatch):
    from app.models.settings import Settings

    expected = _dfp_result()

    class _FakeDFP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, **kwargs):
            # Fresh copy so path stamp on ON path does not mutate OFF comparison source.
            return _dfp_result()

    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.DocumentFirstRetrievalPipeline",
        _FakeDFP,
    )
    monkeypatch.setattr(
        "app.services.evidence_assembly.evidence_assembly_service.DocumentFirstRetrievalPipeline",
        _FakeDFP,
    )

    settings = Settings(
        top_k=5,
        enable_intent_aware_retrieval=False,
        enable_query_expansion=False,
        enable_broad_question_mode=False,
        enable_canonical_source_selection=False,
        enable_context_builder=False,
    )

    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: False,
    )
    off = RetrievalPipelineService(
        MagicMock(), settings, MagicMock(), MagicMock()
    ).run("q", "q")

    monkeypatch.setattr(
        "app.services.retrieval_pipeline_service.evidence_assembly_enabled",
        lambda: True,
    )
    on = RetrievalPipelineService(
        MagicMock(), settings, MagicMock(), MagicMock()
    ).run("q", "q")

    assert [h.url for h in off.hits] == [h.url for h in on.hits]
    assert [h.score for h in off.hits] == [h.score for h in on.hits]
    assert off.diagnostics.quality_metrics == on.diagnostics.quality_metrics
    assert off.diagnostics.retrieval_pipeline_stages == on.diagnostics.retrieval_pipeline_stages
    # Additive marker is the only intentional diagnostics delta.
    off_dict = off.diagnostics.to_dict()
    on_dict = on.diagnostics.to_dict()
    assert off_dict.pop("evidence_assembly_path") == EVIDENCE_ASSEMBLY_PATH_LEGACY
    assert on_dict.pop("evidence_assembly_path") == EVIDENCE_ASSEMBLY_PATH_SERVICE
    assert off_dict == on_dict
    assert expected.selected_hits[0].url == on.hits[0].url


@pytest.mark.unit
def test_evidence_assembly_propagates_dfp_errors(monkeypatch):
    class _BoomDFP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, **kwargs):
            raise RuntimeError("dfp failed")

    monkeypatch.setattr(
        "app.services.evidence_assembly.evidence_assembly_service.DocumentFirstRetrievalPipeline",
        _BoomDFP,
    )
    svc = EvidenceAssemblyService(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    with pytest.raises(RuntimeError, match="dfp failed"):
        svc.assemble(_request())


@pytest.mark.unit
def test_evidence_assembly_does_not_mutate_versions():
    settings = MagicMock()
    settings.knowledge_version = 7
    settings.memory_version = 3
    # Avoid real DFP: patch to no-op after capturing settings identity.
    captured = {}

    class _FakeDFP:
        def __init__(self, db, s, embedding, qdrant) -> None:
            captured["settings"] = s

        def run(self, **kwargs):
            return _dfp_result()

    import app.services.evidence_assembly.evidence_assembly_service as mod

    original = mod.DocumentFirstRetrievalPipeline
    mod.DocumentFirstRetrievalPipeline = _FakeDFP
    try:
        svc = EvidenceAssemblyService(MagicMock(), settings, MagicMock(), MagicMock())
        svc.assemble(_request())
        assert settings.knowledge_version == 7
        assert settings.memory_version == 3
        assert captured["settings"] is settings
    finally:
        mod.DocumentFirstRetrievalPipeline = original


@pytest.mark.unit
def test_evidence_assembly_package_has_no_epistemic_memory_imports():
    forbidden = {
        "epistemic_memory",
        "EpistemicMemory",
        "Claim",
        "Tension",
        "memory_version",
        "MemoryVersion",
    }
    for path in EA_PKG.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "epistemic" not in alias.name.lower()
                    for token in forbidden:
                        assert token not in alias.name
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "epistemic" not in mod.lower()
                assert "claim" not in mod.lower() or "retrieval" in mod.lower()
                for alias in node.names:
                    assert alias.name not in {
                        "EpistemicMemoryService",
                        "ClaimRecord",
                        "TensionView",
                    }


@pytest.mark.unit
def test_evidence_assembly_package_has_no_language_or_llm_imports():
    forbidden_substrings = (
        "llm_generation",
        "ollama_service",
        "prompt_builder",
        "answer_polish",
        "compact_prompt",
        "rag_service",
        "rag_streaming",
    )
    for path in EA_PKG.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
            joined = " ".join(names).lower()
            for bad in forbidden_substrings:
                assert bad not in joined, f"{path.name} imports {bad}"


@pytest.mark.unit
def test_evidence_assembly_thinner_than_rps():
    ea_lines = sum(
        len(p.read_text(encoding="utf-8").splitlines()) for p in EA_PKG.rglob("*.py")
    )
    rps_lines = len(
        (APP_ROOT / "services" / "retrieval_pipeline_service.py")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert ea_lines < rps_lines
    assert ea_lines < 120
