"""RFC-100 Step 056 — golden smoke requires fixture_profile=generic_corporate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from golden import parity_runner
from golden.parity_runner import REQUIRED_FIXTURE_PROFILE, load_golden_smoke

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "queries.json"

_MISSING = object()


def _minimal_smoke(*, fixture_profile) -> dict:
    payload: dict = {
        "version": "1.1",
        "suite": "smoke",
        "queries": [],
    }
    if fixture_profile is not _MISSING:
        payload["fixture_profile"] = fixture_profile
    return payload


@pytest.fixture()
def write_golden(tmp_path, monkeypatch):
    path = tmp_path / "queries.json"

    def _write(*, fixture_profile=_MISSING):
        path.write_text(
            json.dumps(_minimal_smoke(fixture_profile=fixture_profile)),
            encoding="utf-8",
        )
        monkeypatch.setattr(parity_runner, "GOLDEN_PATH", path)
        return path

    return _write


@pytest.mark.unit
def test_current_queries_json_loads_successfully():
    data = load_golden_smoke()
    assert data["suite"] == "smoke"
    assert data["fixture_profile"] == REQUIRED_FIXTURE_PROFILE
    assert GOLDEN_PATH.is_file()


@pytest.mark.unit
def test_fixture_profile_generic_corporate_passes(write_golden):
    write_golden(fixture_profile="generic_corporate")
    data = load_golden_smoke()
    assert data["fixture_profile"] == "generic_corporate"


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture_profile",
    [
        _MISSING,
        None,
        "",
        "bank_financial",
        "ecommerce",
    ],
    ids=["missing", "null", "empty", "bank_financial", "ecommerce"],
)
def test_fixture_profile_rejects_non_generic(write_golden, fixture_profile):
    write_golden(fixture_profile=fixture_profile)
    with pytest.raises(ValueError) as exc_info:
        load_golden_smoke()
    message = str(exc_info.value)
    assert "fixture_profile" in message
    assert "generic_corporate" in message
    if fixture_profile is _MISSING:
        assert "None" in message
    else:
        assert repr(fixture_profile) in message


@pytest.mark.unit
def test_error_includes_expected_and_actual(write_golden):
    write_golden(fixture_profile="saas")
    with pytest.raises(ValueError) as exc_info:
        load_golden_smoke()
    message = str(exc_info.value)
    assert "fixture_profile" in message
    assert "'generic_corporate'" in message
    assert "'saas'" in message
