"""Conservative tension detection from Epistemic Memory reads (RFC-100 Step 034).

Read-only — produces in-memory ``TensionView`` epistemic hypotheses. No
persistence, no chat/retrieval integration, no maintenance execution.

A Tension is not knowledge, not a belief, and not a fact — only a possible-
problem signal inside Epistemic Memory.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.epistemic_memory import EpistemicMemoryService
from app.services.epistemic_memory.types import ClaimView, EvidenceLinkView
from app.services.tension_surfacing.tension_types import (
    TENSION_CONFLICT,
    TENSION_SUPPORT_DEFICIT,
    TensionView,
)

DEFAULT_CLAIM_LIMIT = 500
# Engineering safety bound for operator scrapes / summarize_counts — not a
# cognitive limit on how many tensions can exist in Epistemic Memory. Matches
# DEFAULT_CLAIM_LIMIT so metrics and detection share the same scan ceiling.
# Raising it increases per-scrape DB work (claims + evidence-link lists).
METRICS_CLAIM_SCAN_LIMIT = DEFAULT_CLAIM_LIMIT


@dataclass(frozen=True)
class TensionCountSummary:
    """Bounded count of epistemic hypotheses — not confirmed knowledge errors.

    ``open_tensions`` is the number of surfaced TensionView rows after a scan of
    at most ``claim_scan_limit`` active claims. With the current type set
    (support_deficit + conflict) it equals the sum of the typed counters.
    """

    open_tensions: int
    support_deficit_tensions: int
    conflict_tensions: int
    claim_scan_limit: int


class TensionSurfacingService:
    """Detect support deficits and explicit conflicts from epistemic memory reads."""

    def __init__(self, memory: EpistemicMemoryService) -> None:
        self._memory = memory

    def surface_tensions(self, *, claim_limit: int | None = None) -> list[TensionView]:
        """Return conservative in-memory tensions for active claims."""
        limit = claim_limit if claim_limit is not None else DEFAULT_CLAIM_LIMIT
        claims, _ = self._memory.list_claims(active_only=True, limit=limit)
        if not claims:
            return []

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
                    TensionView(
                        tension_type=TENSION_SUPPORT_DEFICIT,
                        claim_ids=(claim.id,),
                        observation_ref_ids=tuple(
                            sorted({link.observation_ref_id for link in links})
                        ),
                        evidence_link_ids=tuple(sorted(link.id for link in links)),
                        summary=_support_deficit_summary(claim),
                    ),
                )

            for link in conflict_links:
                self._append(
                    tensions,
                    seen,
                    TensionView(
                        tension_type=TENSION_CONFLICT,
                        claim_ids=(claim.id,),
                        observation_ref_ids=(link.observation_ref_id,),
                        evidence_link_ids=(link.id,),
                        summary=_intra_claim_conflict_summary(claim, link),
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
                        TensionView(
                            tension_type=TENSION_CONFLICT,
                            claim_ids=pair,
                            observation_ref_ids=(obs_id,),
                            evidence_link_ids=(
                                link.id,
                                next(
                                    entry_link.id
                                    for cid, entry_link in entries
                                    if cid == supported_id and entry_link.role == "support"
                                ),
                            ),
                            summary=_cross_claim_conflict_summary(
                                supported_id, claim_id, obs_id
                            ),
                        ),
                    )

        return sorted(
            tensions,
            key=lambda t: (
                t.tension_type,
                t.claim_ids,
                t.observation_ref_ids,
                t.evidence_link_ids,
            ),
        )

    def summarize_counts(self, *, claim_limit: int | None = None) -> TensionCountSummary:
        """Return bounded hypothesis counts for operators/metrics.

        Uses the same detection path as ``surface_tensions`` (no rule changes).
        Default scan is capped at ``METRICS_CLAIM_SCAN_LIMIT`` active claims —
        not an unbounded Epistemic Memory walk.
        """
        limit = (
            claim_limit if claim_limit is not None else METRICS_CLAIM_SCAN_LIMIT
        )
        tensions = self.surface_tensions(claim_limit=limit)
        support = sum(1 for t in tensions if t.tension_type == TENSION_SUPPORT_DEFICIT)
        conflict = sum(1 for t in tensions if t.tension_type == TENSION_CONFLICT)
        return TensionCountSummary(
            open_tensions=len(tensions),
            support_deficit_tensions=support,
            conflict_tensions=conflict,
            claim_scan_limit=limit,
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
