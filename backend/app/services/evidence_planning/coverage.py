"""Coverage-aware evidence selection."""
from __future__ import annotations

from app.services.evidence_planning.diversity import diversity_allows
from app.services.evidence_planning.types import (
    EvidenceCandidate,
    RejectedEvidence,
    SelectedEvidence,
)
from app.services.rag_planning.contracts import KnowledgePlan
from app.services.retrieval_engine.focus_compatibility import (
    is_negative_compatibility,
    is_strong_compatibility,
)

_STRONG = frozenset(
    {
        "exact_match",
        "same_product",
        "organization_support",
        "definition_support",
        "procedure_support",
        "navigation_support",
    }
)
_WEAK_AFTER_STRONG = frozenset(
    {
        "category_support",
        "same_category",
        "ambiguous",
        "supporting_evidence",
        "historical",
    }
)


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
    semantic_focus = getattr(knowledge_plan, "semantic_focus", "") or "general"

    pool = sorted(candidates, key=lambda c: c.authority_fitness, reverse=True)
    # Organization profile: never let product pages become primary.
    if semantic_focus == "organization_profile":
        pool = sorted(
            pool,
            key=lambda c: (
                0 if c.page_role == "organization_overview" or c.source_purpose in {
                    "about company",
                    "landing page",
                } else 1,
                -c.authority_fitness,
            ),
        )
    order = 0

    while len(selected) < max_items:
        best: EvidenceCandidate | None = None
        best_value = -1.0
        best_new: tuple[str, ...] = ()
        best_reason = ""

        for cand in pool:
            if any(s.candidate.candidate_id == cand.candidate_id for s in selected):
                continue
            skip_reason = _skip_reason(cand, selected, knowledge_plan)
            if skip_reason:
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
            if is_strong_compatibility(cand.compatibility_label):
                marginal += 0.08
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


def _skip_reason(
    cand: EvidenceCandidate,
    selected: list[SelectedEvidence],
    knowledge_plan: KnowledgePlan,
) -> str:
    if is_negative_compatibility(cand.compatibility_label):
        # Last resort: allow a single adjacent candidate when nothing else can be primary.
        # Never admit news/marketing/historical as primary for strict expected evidence.
        if (
            not selected
            and cand.compatibility_label == "adjacent_incompatible"
            and (getattr(knowledge_plan, "semantic_focus", "") or "")
            in {
                "product_specification",
                "rates",
                "eligibility",
                "definition",
                "locator",
                "contact",
            }
        ):
            return ""
        return "negative_compatibility"
    selected_labels = {item.candidate.compatibility_label for item in selected}
    has_strong = bool(selected_labels & _STRONG)
    focus = getattr(knowledge_plan, "semantic_focus", "") or ""
    if (
        has_strong
        and cand.compatibility_label in _WEAK_AFTER_STRONG
        and focus
        in {
            "product_specification",
            "rates",
            "eligibility",
            "definition",
        }
    ):
        return "weak_after_strong"
    if focus == "organization_profile" and selected:
        if cand.page_role in {"product_details", "pricing", "campaign", "news"}:
            return "entity_inconsistency"
    if has_strong and focus in {"product_specification", "rates", "eligibility"}:
        if cand.compatibility_label in {"same_category", "category_support"}:
            return "product_family_mismatch"
    if focus == "comparison":
        return ""
    expected = getattr(knowledge_plan, "expected_evidence_type", "") or ""
    if (
        expected
        in {
            "organization_profile",
            "definition",
            "locator",
            "product_specification",
            "policy",
            "contact",
        }
        and cand.compatibility_label in {"news_only", "marketing_only", "historical"}
    ):
        return "expected_evidence_mismatch"
    return ""


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
    parts = [
        f"fitness={candidate.authority_fitness:.2f}",
        f"compat={candidate.compatibility_label}",
    ]
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
    skip = _skip_reason(candidate, selected, knowledge_plan)
    if skip == "negative_compatibility":
        if candidate.compatibility_label == "adjacent_incompatible":
            return "adjacent_product_or_scope"
        if candidate.compatibility_label in {"news_only", "marketing_only"}:
            return "expected_evidence_mismatch"
        return candidate.compatibility_label or "negative_compatibility"
    if skip == "entity_inconsistency":
        return "entity_inconsistency"
    if skip == "product_family_mismatch":
        return "product_family_mismatch"
    if skip == "expected_evidence_mismatch":
        return "expected_evidence_mismatch"
    if skip == "weak_after_strong":
        return "lower_marginal_value"
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
