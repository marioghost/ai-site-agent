"""Static boundary guards for Step 046 Memory region read package."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
EPISTEMIC_PKG = APP_ROOT / "services" / "epistemic_memory"
STEP046_MODULES = (
    "memory_region_types.py",
    "memory_region_reader.py",
    "memory_corpus_resolver.py",
)

FORBIDDEN_IMPORT_STEMS = frozenset(
    {
        "app.services.rag_service",
        "app.services.rag_streaming",
        "app.services.reasoning",
        "app.services.evidence_assembly",
        "app.services.retrieval_pipeline_service",
        "app.services.qdrant_service",
        "app.services.ollama_service",
        "app.services.memory_version_service",
        "app.services.knowledge_version_service",
        "app.api",
        "fastapi",
    }
)

CHAT_PATHS = (
    APP_ROOT / "services" / "rag_service.py",
    APP_ROOT / "services" / "rag_streaming.py",
    APP_ROOT / "services" / "reasoning" / "reasoning_service.py",
    APP_ROOT / "api" / "chat.py",
)


def _import_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


@pytest.mark.unit
def test_step046_package_has_no_forbidden_imports():
    violations: list[str] = []
    for name in STEP046_MODULES:
        path = EPISTEMIC_PKG / name
        assert path.is_file(), f"missing {path}"
        imports = _import_modules(path)
        for stem in FORBIDDEN_IMPORT_STEMS:
            for imp in imports:
                if imp == stem or imp.startswith(stem + "."):
                    violations.append(f"{name}: {imp}")
    assert violations == []


@pytest.mark.unit
def test_chat_paths_do_not_import_memory_region_views():
    forbidden_tokens = (
        "MemoryRegionView",
        "MemoryRegionRequest",
        "MemoryCorpusScope",
        "MemoryIsolationScope",
        "MemoryCorpusBoundary",
        "read_region",
        "memory_region_reader",
        "memory_region_types",
        "memory_corpus_resolver",
    )
    violations: list[str] = []
    for path in CHAT_PATHS:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                violations.append(f"{path.name}: {token}")
    assert violations == []
