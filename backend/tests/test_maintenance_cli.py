from __future__ import annotations

import importlib
import sys

import pytest


pytestmark = pytest.mark.unit


def _reload_maintenance():
    sys.modules.pop("app.scripts.maintenance", None)
    return importlib.import_module("app.scripts.maintenance")


def test_maintenance_import_does_not_load_indexing_worker():
    sys.modules.pop("app.services.indexing_worker_service", None)
    mod = _reload_maintenance()
    assert mod is not None
    assert "app.services.indexing_worker_service" not in sys.modules


def test_migrate_command_runs_without_indexing_worker_import(monkeypatch, capsys):
    sys.modules.pop("app.services.indexing_worker_service", None)
    mod = _reload_maintenance()
    monkeypatch.setattr(mod, "upgrade_to_head", lambda: None)
    monkeypatch.setattr(mod, "current_db_revision", lambda: "test_head")
    assert mod.main(["migrate"]) == 0
    assert "app.services.indexing_worker_service" not in sys.modules
    out = capsys.readouterr().out
    assert "database migrated to head" in out
