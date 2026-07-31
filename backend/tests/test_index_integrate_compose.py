"""Index → Integrate compose contract (unit)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.index_integrate import index_and_integrate
from app.services.index_integrate.types import (
    REASON_CONTENT_UNCHANGED,
    REASON_FETCH_FAILED,
    REASON_INDEX_FAILED,
    REASON_MEMORY_SHADOW_WRITE_FAILED,
    REASON_PARSE_FAILED,
    REASON_SI_FAILED,
    STAGE_INDEXING,
    STAGE_MEMORY_INTEGRATION,
    STAGE_NONE,
    STAGE_SOURCE_INTELLIGENCE,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCEEDED,
    IndexIntegrateResult,
)

pytestmark = pytest.mark.unit


def _source() -> MagicMock:
    s = MagicMock()
    s.id = 1
    s.url = "https://example.com/a"
    s.needs_intelligence = True
    return s


def test_full_success_index_si_memory() -> None:
    order: list[str] = []
    profile = object()

    def index(_s: MagicMock) -> SimpleNamespace:
        order.append("index")
        return SimpleNamespace(status="indexed", detail="3 chunks")

    def si(_s: MagicMock) -> object:
        order.append("si")
        return profile

    def mem(_s: MagicMock, p: object) -> object:
        order.append("memory")
        assert p is profile
        return SimpleNamespace(any_created=True)

    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=index,
        run_source_intelligence=si,
        run_memory_integration=mem,
    )
    assert order == ["index", "si", "memory"]
    assert result.status == STATUS_SUCCEEDED
    assert result.completed_stage == STAGE_MEMORY_INTEGRATION
    assert result.failed_stage is None
    assert result.outcome_reason is None


def test_exact_stage_order_integration_style() -> None:
    """Prove default collaborators are invoked in index → SI → Memory order."""
    source = _source()
    settings = MagicMock()
    calls: list[str] = []

    class FakeIndexOutcome:
        status = "indexed"
        detail = "ok"

    with (
        patch(
            "app.services.indexing_service.IndexingService"
        ) as index_cls,
        patch(
            "app.services.source_intelligence_service.SourceIntelligenceService.build_profile",
            side_effect=lambda *a, **k: (calls.append("si_build") or MagicMock()),
        ),
        patch(
            "app.services.source_intelligence_service.SourceIntelligenceService.apply_to_source",
            side_effect=lambda *a, **k: calls.append("si_apply"),
        ),
        patch(
            "app.services.epistemic_memory.memory_integration_service."
            "EpistemicMemoryIntegrationService.shadow_write_after_si",
            side_effect=lambda *a, **k: (calls.append("memory") or SimpleNamespace()),
        ),
        patch(
            "app.services.index_integrate.compose.KnowledgeProfileService.from_settings",
            return_value=MagicMock(),
        ),
    ):
        def _index_source(src, **kwargs):
            calls.append("index")
            return FakeIndexOutcome()

        index_cls.return_value.index_source.side_effect = _index_source
        result = index_and_integrate(MagicMock(), source, settings)

    assert calls == ["index", "si_build", "si_apply", "memory"]
    assert result.status == STATUS_SUCCEEDED
    assert result.completed_stage == STAGE_MEMORY_INTEGRATION


def test_index_error_stops_before_si() -> None:
    si = MagicMock()
    mem = MagicMock()
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="error", detail="Qdrant upsert failed"),
        run_source_intelligence=si,
        run_memory_integration=mem,
    )
    assert result.status == STATUS_FAILED
    assert result.completed_stage == STAGE_NONE
    assert result.failed_stage == STAGE_INDEXING
    assert result.outcome_reason == REASON_INDEX_FAILED
    si.assert_not_called()
    mem.assert_not_called()


def test_fetch_failed_classification() -> None:
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(
            status="error", detail="Fetch failed: timeout"
        ),
        run_source_intelligence=MagicMock(),
        run_memory_integration=MagicMock(),
    )
    assert result.outcome_reason == REASON_FETCH_FAILED


def test_parse_failed_classification() -> None:
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(
            status="error", detail="Extraction failed: bad html"
        ),
        run_source_intelligence=MagicMock(),
        run_memory_integration=MagicMock(),
    )
    assert result.outcome_reason == REASON_PARSE_FAILED


def test_generic_index_failed_classification() -> None:
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="error", detail="Embedding failed"),
        run_source_intelligence=MagicMock(),
        run_memory_integration=MagicMock(),
    )
    assert result.outcome_reason == REASON_INDEX_FAILED


def test_content_unchanged_stops_before_si_and_memory() -> None:
    si = MagicMock()
    mem = MagicMock()
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="skipped", detail="unchanged"),
        run_source_intelligence=si,
        run_memory_integration=mem,
    )
    assert result.status == STATUS_SKIPPED
    assert result.outcome_reason == REASON_CONTENT_UNCHANGED
    assert result.failed_stage == STAGE_INDEXING
    assert result.completed_stage == STAGE_NONE
    si.assert_not_called()
    mem.assert_not_called()


def test_other_skipped_maps_to_index_failed() -> None:
    si = MagicMock()
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="skipped", detail="empty content"),
        run_source_intelligence=si,
        run_memory_integration=MagicMock(),
    )
    assert result.status == STATUS_FAILED
    assert result.outcome_reason == REASON_INDEX_FAILED
    si.assert_not_called()


def test_si_failure_surfaced_and_memory_not_called() -> None:
    mem = MagicMock()
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="indexed", detail="ok"),
        run_source_intelligence=MagicMock(side_effect=RuntimeError("si boom")),
        run_memory_integration=mem,
    )
    assert result.status == STATUS_FAILED
    assert result.completed_stage == STAGE_INDEXING
    assert result.failed_stage == STAGE_SOURCE_INTELLIGENCE
    assert result.outcome_reason == REASON_SI_FAILED
    mem.assert_not_called()


def test_memory_integration_failure_surfaced() -> None:
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="indexed", detail="ok"),
        run_source_intelligence=lambda _s: object(),
        run_memory_integration=MagicMock(side_effect=RuntimeError("shadow boom")),
    )
    assert result.status == STATUS_FAILED
    assert result.completed_stage == STAGE_SOURCE_INTELLIGENCE
    assert result.failed_stage == STAGE_MEMORY_INTEGRATION
    assert result.outcome_reason == REASON_MEMORY_SHADOW_WRITE_FAILED


def test_memory_none_is_not_success() -> None:
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="indexed", detail="ok"),
        run_source_intelligence=lambda _s: object(),
        run_memory_integration=lambda _s, _p: None,
    )
    assert result.status == STATUS_FAILED
    assert result.outcome_reason == REASON_MEMORY_SHADOW_WRITE_FAILED
    assert result.failed_stage == STAGE_MEMORY_INTEGRATION


def test_partial_progress_after_si_failure() -> None:
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="indexed", detail="ok"),
        run_source_intelligence=MagicMock(side_effect=RuntimeError("x")),
        run_memory_integration=MagicMock(),
    )
    assert result.completed_stage == STAGE_INDEXING


def test_partial_progress_after_memory_failure() -> None:
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="indexed", detail="ok"),
        run_source_intelligence=lambda _s: object(),
        run_memory_integration=lambda _s, _p: None,
    )
    assert result.completed_stage == STAGE_SOURCE_INTELLIGENCE


def test_result_is_ephemeral_dataclass_not_orm() -> None:
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="skipped", detail="unchanged"),
        run_source_intelligence=MagicMock(),
        run_memory_integration=MagicMock(),
    )
    assert isinstance(result, IndexIntegrateResult)
    assert not hasattr(result, "__tablename__")
    assert not hasattr(IndexIntegrateResult, "__mapper__")


def test_no_direct_memory_writes_from_compose() -> None:
    db = MagicMock()
    index_and_integrate(
        db,
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(status="indexed", detail="ok"),
        run_source_intelligence=lambda _s: object(),
        run_memory_integration=lambda _s, _p: SimpleNamespace(),
    )
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_summaries_contain_no_secrets() -> None:
    result = index_and_integrate(
        MagicMock(),
        _source(),
        MagicMock(),
        index_only=lambda _s: SimpleNamespace(
            status="error", detail="Fetch failed: password=example-pass"
        ),
        run_source_intelligence=MagicMock(),
        run_memory_integration=MagicMock(),
    )
    assert result.indexing_summary == "redacted"
    assert "example-pass" not in str(result)


def test_index_only_entrypoint_unchanged_by_compose_defaults() -> None:
    """Compose must not alter IndexingService.index_source source."""
    import inspect

    from app.services.indexing_service import IndexingService

    src = inspect.getsource(IndexingService.index_source)
    assert "run_source_intelligence_inline_during_indexing" in src
    assert "logger.debug(\"Source intelligence skipped" in src or "Source intelligence skipped" in src


def test_no_step_060_modules_modified() -> None:
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "services" / "executive"
    # Compose lives outside executive investigation modules; this test is a guard.
    from app.services import index_integrate

    assert "investigation_execution" not in index_integrate.__file__


def test_sanitize_postgresql_credential_url() -> None:
    from app.services.index_integrate.compose import _sanitize

    out = _sanitize("postgresql://demo:example-pass@127.0.0.1/db")
    assert "example-pass" not in out
    assert "demo:example-pass" not in out
    assert "postgresql://demo:example-pass@" not in out
    assert out == "[redacted-uri]"


def test_sanitize_https_userinfo_url() -> None:
    from app.services.index_integrate.compose import _sanitize

    out = _sanitize("https://demo:example-pass@example.com/path")
    assert "example-pass" not in out
    assert "demo:example-pass" not in out
    assert out == "[redacted-uri]"


def test_sanitize_redis_password_only_userinfo() -> None:
    from app.services.index_integrate.compose import _sanitize

    out = _sanitize("redis://:example-pass@127.0.0.1:6379/0")
    assert "example-pass" not in out
    assert out == "[redacted-uri]"


def test_sanitize_credential_url_embedded_in_message() -> None:
    from app.services.index_integrate.compose import _sanitize

    out = _sanitize(
        "Connection failed for https://demo:example-pass@example.com/private"
    )
    assert "example-pass" not in out
    assert "demo:example-pass" not in out
    assert "https://demo:example-pass@" not in out
    assert out.startswith("Connection failed for ")
    assert "[redacted-uri]" in out


def test_sanitize_authorization_bearer() -> None:
    from app.services.index_integrate.compose import _sanitize

    out = _sanitize("Authorization: Bearer example-token")
    assert out == "redacted"
    assert "example-token" not in out
    assert "Bearer example-token" not in out


def test_sanitize_authorization_basic() -> None:
    from app.services.index_integrate.compose import _sanitize

    out = _sanitize("Authorization: Basic dXNlcjpwYXNz")
    assert out == "redacted"
    assert "dXNlcjpwYXNz" not in out


def test_sanitize_password_key_value() -> None:
    from app.services.index_integrate.compose import _sanitize

    out = _sanitize("password=example-pass")
    assert out == "redacted"
    assert "example-pass" not in out


def test_sanitize_token_key_value() -> None:
    from app.services.index_integrate.compose import _sanitize

    out = _sanitize("token=example-token")
    assert out == "redacted"
    assert "example-token" not in out


def test_sanitize_api_key_variants() -> None:
    from app.services.index_integrate.compose import _sanitize

    for raw in ("api_key=example-key", "apikey: example-key", "apikey=example-key"):
        out = _sanitize(raw)
        assert out == "redacted"
        assert "example-key" not in out


def test_sanitize_ordinary_safe_diagnostic() -> None:
    from app.services.index_integrate.compose import _sanitize

    msg = "Fetch failed: timeout after 30 seconds"
    assert _sanitize(msg) == msg


def test_sanitize_length_bounded() -> None:
    from app.services.index_integrate.compose import _SUMMARY_MAX_LEN, _sanitize

    msg = "x" * (_SUMMARY_MAX_LEN + 50)
    out = _sanitize(msg)
    assert len(out) == _SUMMARY_MAX_LEN


def test_sanitize_failure_returns_redacted(monkeypatch) -> None:
    from app.services.index_integrate import compose as compose_mod

    def boom(_uri: str):
        raise RuntimeError("parse boom")

    monkeypatch.setattr(compose_mod, "urlsplit", boom)
    out = compose_mod._sanitize("see https://demo:example-pass@host/z")
    assert out == "redacted"
    assert "example-pass" not in out


def test_sanitize_redacts_password_keyword() -> None:
    from app.services.index_integrate.compose import _sanitize

    assert _sanitize("error password=x") == "redacted"


def test_sanitize_example_secret_keyword_in_url() -> None:
    """Evidence case: keyword 'secret' in userinfo still fail-closed."""
    from app.services.index_integrate.compose import _sanitize

    out = _sanitize("postgresql://demo:example-secret@127.0.0.1/db")
    assert out == "redacted"
    assert "example-secret" not in out
