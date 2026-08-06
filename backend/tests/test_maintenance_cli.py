from __future__ import annotations

import importlib
import sys

import pytest


pytestmark = pytest.mark.unit


def _purge_app_modules() -> None:
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)


def _reload_maintenance():
    _purge_app_modules()
    return importlib.import_module("app.scripts.maintenance")


def test_maintenance_import_does_not_load_indexing_worker():
    mod = _reload_maintenance()
    assert mod is not None
    assert "app.services.indexing_worker_service" not in sys.modules
    assert "app.services.cache_invalidation_service" not in sys.modules


def test_migrate_command_runs_without_heavy_service_imports(monkeypatch, capsys):
    mod = _reload_maintenance()
    monkeypatch.setattr(mod, "upgrade_to_head", lambda: None)
    monkeypatch.setattr(mod, "current_db_revision", lambda: "test_head")
    assert mod.main(["migrate"]) == 0
    assert "app.services.indexing_worker_service" not in sys.modules
    assert "app.services.cache_invalidation_service" not in sys.modules
    out = capsys.readouterr().out
    assert "database migrated to head" in out


def test_source_intelligence_constants_import_does_not_cycle():
    """Fresh process-style import must resolve SI constants without package-init cycles."""
    _purge_app_modules()
    from app.services.source_intelligence_constants import (  # noqa: WPS433
        LOW_OVERVIEW_DOCUMENT_TYPES,
        LOW_OVERVIEW_PAGE_ROLES,
    )

    assert "news_page" in LOW_OVERVIEW_DOCUMENT_TYPES
    assert "news" in LOW_OVERVIEW_PAGE_ROLES


def test_si_constants_to_intent_taxonomy_path_loads():
    _purge_app_modules()
    import app.services.source_intelligence_constants as sic  # noqa: WPS433
    import app.services.source_intelligence_service as sis  # noqa: WPS433

    assert sic.LOW_OVERVIEW_DOCUMENT_TYPES
    assert sis.SourceIntelligenceService is not None
