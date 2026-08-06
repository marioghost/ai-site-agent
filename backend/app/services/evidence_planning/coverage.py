"""Coverage-aware evidence selection."""
from __future__ import annotations

from app.services.evidence_planning.diversity import diversity_allows
from app.services.evidence_planning.types import (
    EvidenceCandidate,
    RejectedEvidence,
    SelectedEvidence,
)
from app.services.rag_planning.contracts import KnowledgePlan


def select_by_coverage(
    candidates: list[EvidenceCandidate],
    *,
    knowledge_plan: KnowledgePlan,
    max_items: int,
    max_per_source: int = 2,
    min_fitness: float = 0.18,
) -> tuple[list[SelectedEvidence], list[RejectedEvidence]]:
    if not candidates:
        return [], []

    required = set(knowledge_plan.required_slots)
    optional = set(knowledge_plan.optional_slots)
    covered: set[str] = set()
    selected: list[SelectedEvidence] = []
    rejected: list[RejectedEvidence] = []
    per_source: dict[int, int] = {}
    used_groups: dict[str, int] = {}

    pool = sorted(candidates, key=lambda c: c.authority_fitness, reverse=True)
    order = 0

    while len(selected) < max_items:
        best: EvidenceCandidate | None = None
        best_value = -1.0
        best_new: tuple[str, ...] = ()
        best_reason = ""

        for cand in pool:
            if any(s.candidate.candidate_id == cand.candidate_id for s in selected):
                continue
            if cand.forbidden_for_query and cand.authority_fitness < 0.45:
                continue
            if cand.authority_fitness < min_fitness and covered & required:
                continue
            if per_source.get(cand.source_id, 0) >= max_per_source:
                continue
            if not diversity_allows(cand, selected, used_groups, knowledge_plan):
                continue

            new_aspects = tuple(sorted(cand.available_aspects - covered))
            req_cover = len(set(new_aspects) & required) / max(len(required), 1)
            opt_cover = len(set(new_aspects) & optional) / max(len(optional), 1) if optional else 0.0
            redundancy = _redundancy_penalty(cand, selected)
            missing_required = required - covered
            support_value = _support_value(cand, selected, missing_required)
            missing_required_bonus = 0.0
            if missing_required and (cand.available_aspects & missing_required):
                missing_required_bonus = 0.10

            marginal = (
                0.32 * cand.authority_fitness
                + 0.33 * req_cover
                + 0.10 * opt_cover
                + 0.14 * cand.section_relevance
                + support_value
                + missing_required_bonus
                - 0.18 * redundancy
            )
            if cand.broad_injected:
                marginal -= 0.14 if selected else 0.08
            if not required and not new_aspects:
                marginal = (
                    0.28 * cand.authority_fitness
                    + 0.18 * cand.section_relevance
                    + support_value
                    - 0.18 * redundancy
                )

            if marginal > best_value:
                best_value = marginal
                best = cand
                best_new = new_aspects
                best_reason = _selection_reason(cand, new_aspects, req_cover)

        stop_threshold = 0.12 if required <= covered else 0.08
        if best is None or best_value < stop_threshold:
            break

        order += 1
        covered |= set(best_new)
        covered |= best.available_aspects & required
        per_source[best.source_id] = per_source.get(best.source_id, 0) + 1
        used_groups[best.duplicate_group] = used_groups.get(best.duplicate_group, 0) + 1
        selected.append(
            SelectedEvidence(
                candidate=best,
                aspects_new=best_new,
                aspects_covered=tuple(sorted(covered & (required | optional))),
                marginal_value=best_value,
                selection_reason=best_reason,
                final_order=order,
            )
        )

    selected_ids = {s.candidate.candidate_id for s in selected}
    for cand in pool:
        if cand.candidate_id in selected_ids:
            continue
        reason = _rejection_reason(cand, selected, knowledge_plan, per_source, max_per_source)
        rejected.append(RejectedEvidence(candidate=cand, rejection_reason=reason))

    return selected, rejected


def _redundancy_penalty(candidate: EvidenceCandidate, selected: list[SelectedEvidence]) -> float:
    if not selected:
        return 0.0
    penalty = 0.0
    for item in selected:
        if item.candidate.source_id == candidate.source_id:
            penalty += 0.35
        if item.candidate.duplicate_group == candidate.duplicate_group:
            penalty += 0.45
        overlap = len(candidate.available_aspects & set(item.candidate.available_aspects))
        if overlap and not (candidate.available_aspects - item.candidate.available_aspects):
            penalty += 0.25
    return min(1.0, penalty)


def _selection_reason(candidate: EvidenceCandidate, new_aspects: tuple[str, ...], req_cover: float) -> str:
    parts = [f"fitness={candidate.authority_fitness:.2f}"]
    if new_aspects:
        parts.append(f"new_aspects={','.join(new_aspects)}")
    if req_cover > 0:
        parts.append("required_aspect_gain")
    if candidate.broad_injected:
        parts.append("broad_inject_candidate")
    if candidate.kp_preferred:
        parts.append("kp_preferred")
    return ";".join(parts)


def _support_value(
    candidate: EvidenceCandidate,
    selected: list[SelectedEvidence],
    missing_required: set[str],
) -> float:
    if not selected:
        return 0.0
    support = 0.0
    if candidate.available_aspects & missing_required:
        support += 0.04
    if candidate.available_aspects and any(
        candidate.available_aspects & set(item.candidate.available_aspects)
        for item in selected
    ):
        support += 0.03
    if all(item.candidate.source_id != candidate.source_id for item in selected):
        support += 0.02
    if candidate.section_relevance >= 0.45:
        support += 0.02
    return min(0.10, support)


def _rejection_reason(
    candidate: EvidenceCandidate,
    selected: list[SelectedEvidence],
    knowledge_plan: KnowledgePlan,
    per_source: dict[int, int],
    max_per_source: int,
) -> str:
    if candidate.forbidden_for_query:
        return "forbidden_aspect_for_intent"
    if per_source.get(candidate.source_id, 0) >= max_per_source:
        return "source_chunk_limit"
    if candidate.authority_fitness < 0.18 and selected:
        return "low_authority_fitness"
    if selected and _redundancy_penalty(candidate, selected) >= 0.7:
        return "redundant_evidence"
    if not selected and candidate.authority_fitness < 0.12:
        return "below_selection_threshold"
    return "lower_marginal_value"
