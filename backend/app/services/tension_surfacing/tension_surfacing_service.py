"""Conservative tension detection from Epistemic Memory reads (RFC-100 Step 034).

Read-only — produces in-memory ``TensionView`` DTOs. No persistence, no chat/retrieval
integration, no maintenance execution.
"""
from __future__ import annotations

from app.services.epistemic_memory import EpistemicMemoryService
from app.services.epistemic_memory.types import ClaimView, EvidenceLinkView
from app.services.tension_surfacing.tension_types import (
    TENSION_CONFLICT,
    TENSION_SUPPORT_DEFICIT,
    TensionView,
)

DEFAULT_CLAIM_LIMIT = 500


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

        return tensions

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
    return f"Active claim lacks supporting evidence: {excerpt!r}"


def _intra_claim_conflict_summary(claim: ClaimView, link: EvidenceLinkView) -> str:
    excerpt = (claim.proposition or "")[:120]
    return (
        f"Claim has explicit conflict evidence (link {link.id}): {excerpt!r}"
    )


def _cross_claim_conflict_summary(
    supported_claim_id: int, conflict_claim_id: int, observation_ref_id: int
) -> str:
    return (
        "Observation "
        f"{observation_ref_id} supports claim {supported_claim_id} "
        f"and conflicts with claim {conflict_claim_id}"
    )
