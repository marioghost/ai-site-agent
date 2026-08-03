"""RFC-100 Step 066 remediation — regressions for Steps 063 / 064 / 065."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


@pytest.mark.unit
def test_step_063_kos_defaults_and_budget_unchanged(monkeypatch):
    """Regression: Step 063 defaults ON; maint investigations budget 0."""
    from app.core.config import get_config
    from app.services import feature_flags as flags
    from app.services.feature_flags import maintenance_observation

    for key in (
        "KNOWLEDGE_OS_EXECUTIVE_ENABLED",
        "REASONING_SERVICE_ENABLED",
        "EVIDENCE_ASSEMBLY_ENABLED",
        "REASONING_SPEECH_ACTS_ENABLED",
        "MAINTENANCE_EXECUTION_ENABLED",
        "MAINTENANCE_INVESTIGATIONS_PER_CYCLE",
    ):
        monkeypatch.delenv(key, raising=False)
    get_config.cache_clear()
    assert flags.knowledge_os_executive_enabled() is True
    assert flags.reasoning_service_enabled() is True
    obs = maintenance_observation()
    assert obs["investigations_per_cycle"] == 0
    get_config.cache_clear()


@pytest.mark.unit
def test_step_064_executive_only_and_dispatch_vocabulary(monkeypatch):
    """Regression: Executive-only API; no legacy vocabulary; 503 detail frozen."""
    from app.api.chat import EXECUTIVE_DISABLED_DETAIL, _dispatch_non_stream_answer
    from app.api.chat_dispatch_log import ChatPath

    allowed = {"executive", "executive_disabled"}
    assert set(ChatPath.__args__) == allowed  # type: ignore[attr-defined]
    assert "legacy" not in allowed

    src = Path(__file__).resolve().parents[1] / "app" / "api" / "chat.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imported.add(f"{node.module}.{alias.name}")
    forbidden = {
        "app.services.rag_service.RagService",
        "app.services.rag_streaming.RagStreamingService",
        "app.services.reasoning.ReasoningService",
    }
    assert not (imported & forbidden)

    monkeypatch.setattr("app.api.chat.knowledge_os_executive_enabled", lambda: False)
    with pytest.raises(HTTPException) as ei:
        _dispatch_non_stream_answer(
            MagicMock(), MagicMock(), "q", "s", request_id="r"
        )
    assert ei.value.status_code == 503
    assert ei.value.detail == EXECUTIVE_DISABLED_DETAIL


@pytest.mark.unit
def test_step_065_flag_definitions_and_build_info_derivation_unchanged():
    """Regression: FLAG_DEFINITIONS registry + build-info derivation intact."""
    from app.services import build_info_service
    from app.services.feature_flags import FLAG_DEFINITIONS, flag_keys

    assert FLAG_DEFINITIONS
    keys = flag_keys()
    assert "KNOWLEDGE_OS_EXECUTIVE_ENABLED" in keys
    src = Path(build_info_service.__file__).read_text(encoding="utf-8")
    assert "FLAG_DEFINITIONS" in src or "flag_definition" in src.lower()
