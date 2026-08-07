"""Tests for single-path Knowledge Profile persistence side effects."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.knowledge_profile_persistence import persist_knowledge_profile
from app.services.knowledge_profile_service import generic_corporate_profile


@pytest.mark.unit
def test_persist_invalidates_and_marks_reprocess(monkeypatch):
    settings = MagicMock()
    saved = MagicMock()
    repo = MagicMock()
    repo.save.return_value = saved
    invalidate = MagicMock()
    reprocess = MagicMock(return_value=3)

    monkeypatch.setattr(
        "app.services.knowledge_profile_persistence.SettingsRepository",
        lambda db: repo,
    )
    monkeypatch.setattr(
        "app.services.knowledge_profile_persistence.CacheInvalidationService",
        lambda db, s: MagicMock(invalidate_for_correctness=invalidate),
    )
    monkeypatch.setattr(
        "app.services.knowledge_profile_persistence.mark_sources_needs_reprocess",
        reprocess,
    )

    profile = generic_corporate_profile()
    profile.organization_name = "Acme"
    out = persist_knowledge_profile(
        MagicMock(), settings, profile, reason="knowledge_profile_generated"
    )

    assert out is saved
    assert isinstance(settings.knowledge_profile_json, str)
    invalidate.assert_called_once_with("knowledge_profile_generated")
    reprocess.assert_called_once()
    assert reprocess.call_args.kwargs["reason"] == "knowledge_profile_generated"
    assert KnowledgeProfile.model_validate_json(settings.knowledge_profile_json)
