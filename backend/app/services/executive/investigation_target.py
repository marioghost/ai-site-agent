"""Target resolution for Step 060 investigations.

Resolves InvestigationPlan → exactly one Source via the ObservationRef graph.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.models.source import Source
from app.repositories.source_repository import SourceRepository
from app.services.epistemic_maintenance import InvestigationPlan
from app.services.epistemic_memory import EpistemicMemoryService
from app.services.executive.investigation_types import (
    REASON_FETCH_DISALLOWED,
    REASON_SOURCE_MISSING,
    REASON_SOURCE_URL_UNAVAILABLE,
    REASON_TARGET_AMBIGUOUS,
    REASON_TARGET_UNRESOLVED,
)
from app.utils.url_utils import is_allowed_domain, is_denied


@dataclass(frozen=True)
class TargetResolution:
    """Outcome of target resolution for one plan."""

    source: Source | None = None
    reason: str | None = None


def resolve_investigation_target(
    db: Session,
    plan: InvestigationPlan,
    settings: Settings,
    *,
    memory: EpistemicMemoryService | None = None,
) -> TargetResolution:
    """Resolve at most one deterministic Source for a plan.

    Ambiguous or empty candidate sets are fail-closed skips.
    """
    memory_svc = memory or EpistemicMemoryService(db)
    candidates = _source_ids_from_observation_refs(memory_svc, plan.observation_ref_ids)
    if not candidates:
        candidates = _source_ids_via_claims(memory_svc, plan.claim_ids)

    if not candidates:
        return TargetResolution(reason=REASON_TARGET_UNRESOLVED)
    if len(candidates) > 1:
        return TargetResolution(reason=REASON_TARGET_AMBIGUOUS)

    source_id = next(iter(candidates))
    source = SourceRepository(db).get(source_id)
    if source is None:
        return TargetResolution(reason=REASON_SOURCE_MISSING)

    url = (source.url or "").strip()
    if not url:
        return TargetResolution(reason=REASON_SOURCE_URL_UNAVAILABLE)

    if not _url_allowed(url, settings):
        return TargetResolution(reason=REASON_FETCH_DISALLOWED)

    return TargetResolution(source=source)


def _source_ids_from_observation_refs(
    memory: EpistemicMemoryService,
    observation_ref_ids: tuple[int, ...],
) -> set[int]:
    ids: set[int] = set()
    for obs_id in observation_ref_ids:
        view = memory.get_observation_ref(observation_ref_id=obs_id)
        if view is not None and view.source_id is not None:
            ids.add(int(view.source_id))
    return ids


def _source_ids_via_claims(
    memory: EpistemicMemoryService,
    claim_ids: tuple[int, ...],
) -> set[int]:
    ids: set[int] = set()
    for claim_id in claim_ids:
        links, _total = memory.list_evidence_links_for_claim(claim_id)
        for link in links:
            view = memory.get_observation_ref(observation_ref_id=link.observation_ref_id)
            if view is not None and view.source_id is not None:
                ids.add(int(view.source_id))
    return ids


def _url_allowed(url: str, settings: Settings) -> bool:
    try:
        allowed = json.loads(settings.allowed_domains_json or "[]")
    except json.JSONDecodeError:
        allowed = []
    try:
        deny = json.loads(settings.deny_url_patterns_json or "[]")
    except json.JSONDecodeError:
        deny = []
    if not isinstance(allowed, list):
        allowed = []
    if not isinstance(deny, list):
        deny = []
    # Empty allow-list means unrestricted (same semantics as CrawlFrontier / url_utils).
    if allowed and not is_allowed_domain(url, [str(a) for a in allowed]):
        return False
    if deny and is_denied(url, [str(p) for p in deny]):
        return False
    return True
