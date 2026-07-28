"""Advisory Memory evidence assist policy (RFC-100 Step 047)."""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.services.epistemic_memory.epistemic_memory_service import EpistemicMemoryService
from app.services.epistemic_memory.memory_corpus_resolver import resolve_deployment_boundary
from app.services.epistemic_memory.memory_region_types import (
    LIMIT_CORPUS_SCOPE_UNCONFIGURED,
    LIMIT_SPARSE_MEMORY,
    SPARSE_MEMORY_THRESHOLD,
)
from app.services.feature_flags import (
    cache_namespace_v2_enabled,
    memory_evidence_assist_enabled,
    reasoning_service_enabled,
)
from app.services.memory_version_service import MemoryVersionService
from app.services.reasoning.memory_assist_types import (
    SKIP_CACHE_NAMESPACE_V2_REQUIRED,
    SKIP_CORPUS_UNCONFIGURED,
    SKIP_REASONING_DISABLED,
    MemoryAssistResult,
)
from app.services.reasoning.memory_request_builder import build_memory_region_request

if TYPE_CHECKING:
    from app.services.retrieval_pipeline_service import PreparedRetrieval

logger = logging.getLogger(__name__)

_MEMORY_READ_TIMEOUT_SECONDS = 2.0


def corpus_boundary_fingerprint_for_settings(settings: Settings) -> str | None:
    """Deterministic corpus fingerprint for cache namespace (no DB claim reads)."""
    boundary = resolve_deployment_boundary(settings)
    if not boundary.configured:
        return None
    return boundary.fingerprint()


def memory_assist_effective(settings: Settings) -> bool:
    """True when assist is configured to affect cache namespace and reads."""
    return (
        reasoning_service_enabled()
        and memory_evidence_assist_enabled(settings)
        and cache_namespace_v2_enabled(settings)
    )


class MemoryAssistPolicy:
    """Owns one advisory read_region() per turn — fail-open, no writes."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def attempt(
        self,
        prepared: PreparedRetrieval,
        settings: Settings,
    ) -> MemoryAssistResult:
        if not memory_evidence_assist_enabled(settings):
            return MemoryAssistResult.off()
        if not reasoning_service_enabled():
            return MemoryAssistResult.skipped(SKIP_REASONING_DISABLED)
        if not cache_namespace_v2_enabled(settings):
            return MemoryAssistResult.skipped(SKIP_CACHE_NAMESPACE_V2_REQUIRED)

        boundary = resolve_deployment_boundary(settings)
        fingerprint = boundary.fingerprint() if boundary.configured else None
        if not boundary.configured:
            return MemoryAssistResult(
                attempted=True,
                path="empty",
                region_found=False,
                matched_claim_count=0,
                supported_claim_count=0,
                conflicted_claim_count=0,
                source_ids=(),
                observation_ref_ids=(),
                topic_hints=(),
                page_role_hints=(),
                limitations=(),
                corpus_limitations=(LIMIT_CORPUS_SCOPE_UNCONFIGURED,),
                corpus_scope_configured=False,
                corpus_scope_complete=False,
                completeness_unknown=True,
                usable_for_evidence=False,
                assist_reason="deployment_corpus_unconfigured",
                skipped_reason=SKIP_CORPUS_UNCONFIGURED,
                memory_read_duration_ms=0,
                memory_version=self._read_memory_version(settings),
                corpus_boundary_fingerprint=fingerprint,
            )

        request = build_memory_region_request(prepared)
        started = time.perf_counter()
        try:
            view = self._read_region_with_timeout(request)
        except FuturesTimeoutError:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.warning("memory_assist_timeout duration_ms=%s", duration_ms)
            return MemoryAssistResult(
                attempted=True,
                path="failed",
                region_found=False,
                matched_claim_count=0,
                supported_claim_count=0,
                conflicted_claim_count=0,
                source_ids=(),
                observation_ref_ids=(),
                topic_hints=request.normalized_topic_key() and (request.normalized_topic_key(),) or (),
                page_role_hints=request.normalized_page_roles() and tuple(sorted(request.normalized_page_roles())) or (),
                limitations=("memory_read_timeout",),
                corpus_limitations=(),
                corpus_scope_configured=True,
                corpus_scope_complete=True,
                completeness_unknown=True,
                usable_for_evidence=False,
                assist_reason="memory_read_timeout",
                memory_read_duration_ms=duration_ms,
                memory_version=self._read_memory_version(settings),
                corpus_boundary_fingerprint=fingerprint,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.warning(
                "memory_assist_failed error_type=%s duration_ms=%s",
                type(exc).__name__,
                duration_ms,
            )
            return MemoryAssistResult(
                attempted=True,
                path="failed",
                region_found=False,
                matched_claim_count=0,
                supported_claim_count=0,
                conflicted_claim_count=0,
                source_ids=(),
                observation_ref_ids=(),
                topic_hints=(),
                page_role_hints=(),
                limitations=(f"memory_read_error:{type(exc).__name__}",),
                corpus_limitations=(),
                corpus_scope_configured=True,
                corpus_scope_complete=True,
                completeness_unknown=True,
                usable_for_evidence=False,
                assist_reason="memory_read_failed",
                memory_read_duration_ms=duration_ms,
                memory_version=self._read_memory_version(settings),
                corpus_boundary_fingerprint=fingerprint,
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        return self._view_to_result(view, settings, duration_ms, fingerprint)

    def _read_region_with_timeout(self, request):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                EpistemicMemoryService(self._db).read_region,
                request,
            )
            return future.result(timeout=_MEMORY_READ_TIMEOUT_SECONDS)

    def _read_memory_version(self, settings: Settings) -> int | None:
        if not cache_namespace_v2_enabled(settings):
            return None
        return MemoryVersionService(self._db).get()

    def _view_to_result(
        self,
        view,
        settings: Settings,
        duration_ms: int,
        fingerprint: str | None,
    ) -> MemoryAssistResult:
        matched = view.total_matched
        supported = 0
        conflicted = 0
        source_ids: set[int] = set()
        observation_ids: set[int] = set()
        claim_ids: list[int] = []

        for claim in view.matched_claims:
            claim_ids.append(claim.claim_id)
            if not claim.evidence_loaded:
                continue
            if claim.has_support:
                supported += 1
            if claim.has_conflict:
                conflicted += 1
            for ref in claim.evidence:
                if ref.source_id is not None:
                    source_ids.add(ref.source_id)
                observation_ids.add(ref.observation_ref_id)

        usable = supported > 0 and bool(observation_ids)
        limitations = tuple(view.limitations)
        corpus_limitations = tuple(view.corpus_limitations)

        if matched == 0:
            path = "empty"
            assist_reason = "no_matching_claims"
        elif matched < SPARSE_MEMORY_THRESHOLD or LIMIT_SPARSE_MEMORY in limitations:
            path = "sparse"
            assist_reason = "sparse_memory_region"
        else:
            path = "used"
            assist_reason = "memory_region_matched"

        request = view.request_echo
        topic_hints = ()
        if request.normalized_topic_key():
            topic_hints = (request.normalized_topic_key(),)
        page_roles = request.normalized_page_roles()
        page_role_hints = tuple(sorted(page_roles)) if page_roles else ()

        return MemoryAssistResult(
            attempted=True,
            path=path,
            region_found=matched > 0,
            matched_claim_count=matched,
            supported_claim_count=supported,
            conflicted_claim_count=conflicted,
            source_ids=tuple(sorted(source_ids)),
            observation_ref_ids=tuple(sorted(observation_ids)),
            topic_hints=topic_hints,
            page_role_hints=page_role_hints,
            limitations=limitations,
            corpus_limitations=corpus_limitations,
            corpus_scope_configured=view.corpus_scope_configured,
            corpus_scope_complete=view.corpus_scope_complete,
            completeness_unknown=view.completeness_unknown,
            usable_for_evidence=usable,
            assist_reason=assist_reason,
            memory_read_duration_ms=duration_ms,
            memory_version=self._read_memory_version(settings),
            claim_ids=tuple(claim_ids),
            corpus_boundary_fingerprint=fingerprint or view.corpus_boundary_fingerprint(),
        )
