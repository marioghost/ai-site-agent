"""Authoritative Single-Source Index → Integrate compose (additive).

Sequences: index-only primitive → Source Intelligence → Memory Integration.
Does not change index-only / admin / full-site caller semantics.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.models.source import Source
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
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.utils.time_utils import utcnow

_SUMMARY_MAX_LEN = 200
_SECRET_KEYWORDS = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
)
# Any absolute URI; credential check uses urlsplit userinfo.
_URI_RE = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s]+)")

IndexOnlyFn = Callable[[Source], Any]
SourceIntelligenceFn = Callable[[Source], Any]
MemoryIntegrationFn = Callable[[Source, Any], Any]


def index_and_integrate(
    db: Session,
    source: Source,
    settings: Settings,
    *,
    index_only: IndexOnlyFn | None = None,
    run_source_intelligence: SourceIntelligenceFn | None = None,
    run_memory_integration: MemoryIntegrationFn | None = None,
) -> IndexIntegrateResult:
    """Explicit Index → Integrate compose entry (opt-in).

    Concrete collaborators are injectable for tests; defaults bind existing
    authoritative boundaries without changing index-only callers.
    """
    index_fn = index_only or _default_index_only(db, settings)
    si_fn = run_source_intelligence or _default_source_intelligence(db, settings)
    mem_fn = run_memory_integration or _default_memory_integration(db, settings)

    try:
        index_outcome = index_fn(source)
    except Exception as exc:  # noqa: BLE001
        return IndexIntegrateResult(
            status=STATUS_FAILED,
            completed_stage=STAGE_NONE,
            failed_stage=STAGE_INDEXING,
            outcome_reason=_classify_index_exception(exc),
            indexing_summary=_sanitize(f"{type(exc).__name__}"),
            source_intelligence_summary=None,
            memory_summary=None,
        )

    index_status = str(getattr(index_outcome, "status", "") or "").strip().lower()
    index_detail = str(getattr(index_outcome, "detail", "") or "")
    indexing_summary = _opaque_pair(index_status, index_detail)

    if index_status == "error":
        return IndexIntegrateResult(
            status=STATUS_FAILED,
            completed_stage=STAGE_NONE,
            failed_stage=STAGE_INDEXING,
            outcome_reason=_classify_index_detail(index_detail),
            indexing_summary=indexing_summary,
            source_intelligence_summary=None,
            memory_summary=None,
        )

    if index_status == "skipped":
        detail_l = index_detail.lower()
        if "unchanged" in detail_l:
            return IndexIntegrateResult(
                status=STATUS_SKIPPED,
                completed_stage=STAGE_NONE,
                failed_stage=STAGE_INDEXING,
                outcome_reason=REASON_CONTENT_UNCHANGED,
                indexing_summary=indexing_summary,
                source_intelligence_summary=None,
                memory_summary=None,
            )
        return IndexIntegrateResult(
            status=STATUS_FAILED,
            completed_stage=STAGE_NONE,
            failed_stage=STAGE_INDEXING,
            outcome_reason=REASON_INDEX_FAILED,
            indexing_summary=indexing_summary,
            source_intelligence_summary=None,
            memory_summary=None,
        )

    if index_status != "indexed":
        return IndexIntegrateResult(
            status=STATUS_FAILED,
            completed_stage=STAGE_NONE,
            failed_stage=STAGE_INDEXING,
            outcome_reason=REASON_INDEX_FAILED,
            indexing_summary=indexing_summary,
            source_intelligence_summary=None,
            memory_summary=None,
        )

    # --- Source Intelligence (mandatory; must not swallow) ---
    try:
        profile = si_fn(source)
    except Exception as exc:  # noqa: BLE001
        return IndexIntegrateResult(
            status=STATUS_FAILED,
            completed_stage=STAGE_INDEXING,
            failed_stage=STAGE_SOURCE_INTELLIGENCE,
            outcome_reason=REASON_SI_FAILED,
            indexing_summary=indexing_summary,
            source_intelligence_summary=_sanitize(type(exc).__name__),
            memory_summary=None,
        )

    si_summary = _sanitize("source_intelligence_ok")

    # --- Memory Integration (mandatory; None/unavailable = failure) ---
    try:
        memory_result = mem_fn(source, profile)
    except Exception as exc:  # noqa: BLE001
        return IndexIntegrateResult(
            status=STATUS_FAILED,
            completed_stage=STAGE_SOURCE_INTELLIGENCE,
            failed_stage=STAGE_MEMORY_INTEGRATION,
            outcome_reason=REASON_MEMORY_SHADOW_WRITE_FAILED,
            indexing_summary=indexing_summary,
            source_intelligence_summary=si_summary,
            memory_summary=_sanitize(type(exc).__name__),
        )

    if memory_result is None:
        return IndexIntegrateResult(
            status=STATUS_FAILED,
            completed_stage=STAGE_SOURCE_INTELLIGENCE,
            failed_stage=STAGE_MEMORY_INTEGRATION,
            outcome_reason=REASON_MEMORY_SHADOW_WRITE_FAILED,
            indexing_summary=indexing_summary,
            source_intelligence_summary=si_summary,
            memory_summary=_sanitize("memory_integration_unavailable"),
        )

    return IndexIntegrateResult(
        status=STATUS_SUCCEEDED,
        completed_stage=STAGE_MEMORY_INTEGRATION,
        failed_stage=None,
        outcome_reason=None,
        indexing_summary=indexing_summary,
        source_intelligence_summary=si_summary,
        memory_summary=_sanitize("memory_integration_ok"),
    )


def _default_index_only(db: Session, settings: Settings) -> IndexOnlyFn:
    def _call(source: Source) -> Any:
        from app.services.indexing_service import IndexingService

        return IndexingService(db, settings).index_source(source)

    return _call


def _default_source_intelligence(db: Session, settings: Settings) -> SourceIntelligenceFn:
    def _call(source: Source) -> Any:
        from app.services.source_intelligence_service import SourceIntelligenceService

        profile = KnowledgeProfileService.from_settings(settings)
        sp = SourceIntelligenceService.build_profile(
            source, profile, settings=settings, db=db
        )
        SourceIntelligenceService.apply_to_source(
            source, sp, settings=settings, now=utcnow()
        )
        source.needs_intelligence = False
        return sp

    return _call


def _default_memory_integration(db: Session, settings: Settings) -> MemoryIntegrationFn:
    def _call(source: Source, profile: Any) -> Any:
        from app.services.epistemic_memory.memory_integration_service import (
            EpistemicMemoryIntegrationService,
        )

        return EpistemicMemoryIntegrationService(db, settings).shadow_write_after_si(
            source, profile
        )

    return _call


def _classify_index_detail(detail: str) -> str:
    d = detail.lower()
    if "fetch failed" in d or d.startswith("fetch "):
        return REASON_FETCH_FAILED
    if "extraction failed" in d or "parse" in d:
        return REASON_PARSE_FAILED
    return REASON_INDEX_FAILED


def _classify_index_exception(exc: BaseException) -> str:
    msg = str(exc).lower()
    if "fetch" in msg:
        return REASON_FETCH_FAILED
    if "parse" in msg or "extract" in msg:
        return REASON_PARSE_FAILED
    return REASON_INDEX_FAILED


def _opaque_pair(status: str, detail: str) -> str:
    status = status.strip()
    detail = detail.strip()
    if status and detail:
        return _sanitize(f"{status}: {detail}")
    return _sanitize(status or detail or "")


def _sanitize(value: str) -> str:
    """Keep summaries short and non-secret. Fail closed to ``redacted``."""
    try:
        text = " ".join(str(value).split())
        if not text:
            return ""

        lowered = text.lower()
        for needle in _SECRET_KEYWORDS:
            if needle in lowered:
                return "redacted"

        scrubbed = _URI_RE.sub(_scrub_uri_match, text)

        # Fail closed: any remaining scheme://…@ userinfo pattern.
        if re.search(r"://[^/\s]*@", scrubbed):
            return "redacted"

        if len(scrubbed) > _SUMMARY_MAX_LEN:
            return scrubbed[:_SUMMARY_MAX_LEN]
        return scrubbed
    except Exception:  # noqa: BLE001
        return "redacted"


def _scrub_uri_match(match: re.Match[str]) -> str:
    raw = match.group(0)
    uri = raw
    trailing = ""
    while uri and uri[-1] in ".,;:)]}":
        trailing = uri[-1] + trailing
        uri = uri[:-1]
    parts = urlsplit(uri)
    if parts.username is not None or parts.password is not None:
        return "[redacted-uri]" + trailing
    netloc = parts.netloc or ""
    if "@" in netloc:
        # Ambiguous userinfo — fail closed for this URI.
        return "[redacted-uri]" + trailing
    return raw
