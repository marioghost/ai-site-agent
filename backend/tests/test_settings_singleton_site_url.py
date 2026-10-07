"""Wave A — Settings singleton + generic site_url backfill."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.repositories.settings_repository import SettingsRepository
from app.services.site_origin_service import SiteOriginService

pytestmark = pytest.mark.unit


def test_origin_from_url_strips_www() -> None:
    assert (
        SiteOriginService.origin_from_url("https://www.Example.com/path")
        == "https://example.com"
    )
    assert SiteOriginService.origin_from_url("not-a-url") is None


def test_dominant_origin_picks_majority() -> None:
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [
        "https://www.acme.test/a",
        "https://acme.test/b",
        "https://other.test/c",
        "https://acme.test/d",
    ]
    assert SiteOriginService(db).dominant_origin() == "https://acme.test"


def test_ensure_site_url_persists_when_empty(monkeypatch) -> None:
    settings = SimpleNamespace(id=1, site_url=None)
    db = MagicMock()
    repo = SettingsRepository(db)

    monkeypatch.setattr(
        "app.services.site_origin_service.SiteOriginService.dominant_origin",
        lambda self: "https://acme.test",
    )
    out = repo.ensure_site_url(settings)  # type: ignore[arg-type]
    assert out.site_url == "https://acme.test"
    db.add.assert_called()
    db.commit.assert_called()


def test_ensure_site_url_noop_when_set(monkeypatch) -> None:
    settings = SimpleNamespace(id=1, site_url="https://already.set/")
    db = MagicMock()
    repo = SettingsRepository(db)
    called = {"n": 0}

    def boom(self):
        called["n"] += 1
        raise AssertionError("should not infer")

    monkeypatch.setattr(
        "app.services.site_origin_service.SiteOriginService.dominant_origin",
        boom,
    )
    out = repo.ensure_site_url(settings)  # type: ignore[arg-type]
    assert out.site_url == "https://already.set/"
    assert called["n"] == 0


def test_prune_extra_rows_deletes_non_keepers() -> None:
    db = MagicMock()
    db.execute.return_value.rowcount = 1
    repo = SettingsRepository(db)
    repo._prune_extra_rows(keep_id=1)
    db.commit.assert_called_once()
