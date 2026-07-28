"""Conservative tension detection from Epistemic Memory reads (RFC-100 Step 034).

Read-only — produces in-memory ``TensionView`` epistemic hypotheses. No
persistence, no chat/retrieval integration, no maintenance execution.

A Tension is not knowledge, not a belief, and not a fact — only a possible-
problem signal inside Epistemic Memory.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from app.services.epistemic_memory import EpistemicMemoryService
from app.services.epistemic_memory.provenance_scope import (
    ProvenanceScope,
    classify_tension_scope,
    is_test_claim,
    tension_matches_scope,
)
from app.services.epistemic_memory.types import ClaimView, EvidenceLinkView
from app.services.tension_surfacing.tension_types import (
    TENSION_CONFLICT,
    TENSION_SUPPORT_DEFICIT,
    TensionView,
)

DEFAULT_CLAIM_LIMIT = 500
METRICS_CLAIM_SCAN_LIMIT = DEFAULT_CLAIM_LIMIT


@dataclass(frozen=True)
class TensionCountSummary:
    """Bounded count of epistemic hypotheses — not confirmed knowledge errors."""

    open_tensions: int
    support_deficit_tensions: int
    conflict_tensions: int
    claim_scan_limit: int
    provenance_scope: str = ProvenanceScope.ALL.value


class TensionSurfacingService:
    """Detect support deficits and explicit conflicts from epistemic memory reads."""

    def __init__(self, memory: EpistemicMemoryService) -> None:
        self._memory = memory

    def surface_tensions(
        self,
        *,
        claim_limit: int | None = None,
        provenance_scope: ProvenanceScope | str = ProvenanceScope.ALL,
    ) -> list[TensionView]:
        """Return conservative in-memory tensions for active claims."""
        if isinstance(provenance_scope, str):
            provenance_scope = ProvenanceScope(provenance_scope)
        limit = claim_limit if claim_limit is not None else DEFAULT_CLAIM_LIMIT
        claims, _ = self._memory.list_claims(
            active_only=True,
            limit=limit,
            provenance_scope=provenance_scope
            if provenance_scope is not ProvenanceScope.ALL
            else ProvenanceScope.ALL,
        )
        # When filtering real/test, still load matching claims only.
        # For ALL, list_claims without scope filter (ALL).
        if not claims:
            return []

        claim_by_id = {c.id: c for c in claims}
        claim_links: dict[int, list[EvidenceLinkView]] = {}
        obs_index: dict[int, list[tuple[int, EvidenceLinkView]]] = {}

        for claim in claims:
            links, _ = self._memory.list_evidence_links_for_claim(claim.id)
            claim_links[claim.id] = links
            for link in links:
                obs_index.setdefault(link.observation_ref_id, []).append((claim.id, link))

        tensions: list[TensionView] = []
        seen: set[tuple[str, tuple[int, ...], tuple[int, ...]]] = set()

        for claim in claims:
            links = claim_links.get(claim.id, [])
            support_links = [link for link in links if link.role == "support"]
            conflict_links = [link for link in links if link.role == "conflict"]

            if not support_links:
                self._append(
                    tensions,
                    seen,
                    self._annotate(
                        TensionView(
                            tension_type=TENSION_SUPPORT_DEFICIT,
                            claim_ids=(claim.id,),
                            observation_ref_ids=tuple(
                                sorted({link.observation_ref_id for link in links})
                            ),
                            evidence_link_ids=tuple(sorted(link.id for link in links)),
                            summary=_support_deficit_summary(claim),
                        ),
                        claim_by_id,
                    ),
                )

            for link in conflict_links:
                self._append(
                    tensions,
                    seen,
                    self._annotate(
                        TensionView(
                            tension_type=TENSION_CONFLICT,
                            claim_ids=(claim.id,),
                            observation_ref_ids=(link.observation_ref_id,),
                            evidence_link_ids=(link.id,),
                            summary=_intra_claim_conflict_summary(claim, link),
                        ),
                        claim_by_id,
                    ),
                )

        for obs_id, entries in obs_index.items():
            support_claims = {cid for cid, link in entries if link.role == "support"}
            for claim_id, link in entries:
                if link.role != "conflict":
                    continue
                for supported_id in support_claims:
                    if supported_id == claim_id:
                        continue
                    pair = tuple(sorted((supported_id, claim_id)))
                    self._append(
                        tensions,
                        seen,
                        self._annotate(
                            TensionView(
                                tension_type=TENSION_CONFLICT,
                                claim_ids=pair,
                                observation_ref_ids=(obs_id,),
                                evidence_link_ids=(
                                    link.id,
                                    next(
                                        entry_link.id
                                        for cid, entry_link in entries
                                        if cid == supported_id
                                        and entry_link.role == "support"
                                    ),
                                ),
                                summary=_cross_claim_conflict_summary(
                                    supported_id, claim_id, obs_id
                                ),
                            ),
                            claim_by_id,
                        ),
                    )

        if provenance_scope is not ProvenanceScope.ALL:
            tensions = [
                t
                for t in tensions
                if tension_matches_scope(t.provenance_scope, provenance_scope)
            ]

        return sorted(
            tensions,
            key=lambda t: (
                t.tension_type,
                t.claim_ids,
                t.observation_ref_ids,
                t.evidence_link_ids,
            ),
        )

    def summarize_counts(
        self,
        *,
        claim_limit: int | None = None,
        provenance_scope: ProvenanceScope | str = ProvenanceScope.ALL,
    ) -> TensionCountSummary:
        """Return bounded hypothesis counts for operators/metrics.

        Default ``provenance_scope=all`` preserves historical metric continuity.
        Epistemic Health API uses ``real`` explicitly.
        """
        if isinstance(provenance_scope, str):
            provenance_scope = ProvenanceScope(provenance_scope)
        limit = (
            claim_limit if claim_limit is not None else METRICS_CLAIM_SCAN_LIMIT
        )
        tensions = self.surface_tensions(
            claim_limit=limit, provenance_scope=provenance_scope
        )
        support = sum(1 for t in tensions if t.tension_type == TENSION_SUPPORT_DEFICIT)
        conflict = sum(1 for t in tensions if t.tension_type == TENSION_CONFLICT)
        return TensionCountSummary(
            open_tensions=len(tensions),
            support_deficit_tensions=support,
            conflict_tensions=conflict,
            claim_scan_limit=limit,
            provenance_scope=provenance_scope.value,
        )

    @staticmethod
    def _annotate(
        tension: TensionView, claim_by_id: dict[int, ClaimView]
    ) -> TensionView:
        kinds: list[str] = []
        test_flags: list[bool] = []
        for cid in tension.claim_ids:
            claim = claim_by_id.get(cid)
            if claim is None:
                kinds.append("unknown")
                test_flags.append(False)
                continue
            kinds.append(claim.provenance_kind)
            test_flags.append(
                is_test_claim(
                    provenance_kind=claim.provenance_kind,
                    attributed_to=claim.attributed_to,
                )
            )
        scope = classify_tension_scope(test_flags)
        return replace(
            tension,
            provenance_scope=scope,
            claim_provenance_kinds=tuple(kinds),
            is_test_data=scope == ProvenanceScope.TEST.value,
        )

    @staticmethod
    def _append(
        tensions: list[TensionView],
        seen: set[tuple[str, tuple[int, ...], tuple[int, ...]]],
        tension: TensionView,
    ) -> None:
        key = (tension.tension_type, tension.claim_ids, tension.observation_ref_ids)
        if key in seen:
            return
        seen.add(key)
        tensions.append(tension)


def _support_deficit_summary(claim: ClaimView) -> str:
    excerpt = (claim.proposition or "")[:120]
    return (
        "Possible support deficit: active claim has no supporting evidence: "
        f"{excerpt!r}"
    )


def _intra_claim_conflict_summary(claim: ClaimView, link: EvidenceLinkView) -> str:
    excerpt = (claim.proposition or "")[:120]
    return (
        "Possible conflict: claim has explicit conflict evidence "
        f"(link {link.id}): {excerpt!r}"
    )


def _cross_claim_conflict_summary(
    supported_claim_id: int, conflict_claim_id: int, observation_ref_id: int
) -> str:
    return (
        "Possible conflict: observation "
        f"{observation_ref_id} supports claim {supported_claim_id} "
        f"and conflicts with claim {conflict_claim_id}"
    )
