"""Pre-LLM evidence sufficiency from the evidence plan."""
from __future__ import annotations

from app.services.evidence_planning.types import (
    EvidencePlanSufficiency,
    SelectedEvidence,
    SufficiencyLevel,
)
from app.services.rag_planning.contracts import KnowledgePlan
from app.services.retrieval_engine.focus_compatibility import is_strong_compatibility


def assess_plan_sufficiency(
    selected: list[SelectedEvidence],
    *,
    knowledge_plan: KnowledgePlan,
    contradiction_count: int = 0,
    budget_truncated: bool = False,
) -> EvidencePlanSufficiency:
    if not selected:
        return EvidencePlanSufficiency(
            level="no_evidence",
            required_aspects_covered=(),
            required_aspects_missing=knowledge_plan.required_slots,
            reasons=("no_evidence_selected",),
            goal_satisfaction=0.0,
            expected_evidence_matched=False,
        )

    covered: set[str] = set()
    for item in selected:
        covered |= set(item.aspects_new)
        covered |= item.candidate.available_aspects

    required = set(knowledge_plan.required_slots)
    covered_required = tuple(sorted(required & covered))
    missing_required = tuple(sorted(required - covered))

    avg_fitness = sum(s.candidate.authority_fitness for s in selected) / len(selected)
    incidental_only = all(s.candidate.fitness_band in {"low", "poor"} for s in selected)
    inject_heavy = (
        len(selected) > 1
        and sum(1 for s in selected if s.candidate.broad_injected) >= len(selected)
    )
    labels = [s.candidate.compatibility_label for s in selected]
    expected_matched = any(is_strong_compatibility(label) for label in labels)
    focus = getattr(knowledge_plan, "semantic_focus", "") or "general"
    expected = getattr(knowledge_plan, "expected_evidence_type", "") or "general"
    weak_only = all(
        label in {"news_only", "marketing_only", "historical", "ambiguous", "adjacent_incompatible"}
        for label in labels
    )
    homepage_only = all(
        s.candidate.page_role in {"organization_overview", "generic", "marketing"}
        or s.candidate.document_type in {"homepage", "landing_page"}
        for s in selected
    ) and focus in {"definition", "product_specification", "rates", "locator"}

    slot_ratio = (
        len(covered_required) / max(len(required), 1) if required else (1.0 if selected else 0.0)
    )
    goal = 0.35 * slot_ratio + 0.35 * min(1.0, avg_fitness) + (0.30 if expected_matched else 0.0)
    if weak_only or homepage_only:
        goal = min(goal, 0.28)
        expected_matched = False

    reasons: list[str] = []
    level: SufficiencyLevel

    if focus in {"definition", "product_specification", "rates", "locator", "organization_profile"}:
        if not expected_matched or weak_only or homepage_only:
            level = "weak" if (weak_only or homepage_only or not selected) else "partial"
            reasons.append("expected_evidence_not_matched")
            if homepage_only:
                reasons.append("homepage_or_generic_only")
            if weak_only:
                reasons.append("news_or_marketing_only")
        elif not missing_required and avg_fitness >= 0.42:
            level = "sufficient"
            reasons.append("required_aspects_covered")
            reasons.append("expected_evidence_matched")
        elif missing_required:
            level = "partial"
            reasons.append("missing_required_aspects")
        else:
            level = "partial"
            reasons.append("moderate_authority_only")
    elif not missing_required and avg_fitness >= 0.42:
        level = "sufficient"
        reasons.append("required_aspects_covered")
    elif missing_required and avg_fitness >= 0.55:
        level = "partial"
        reasons.append("missing_required_aspects")
    elif missing_required:
        level = "weak"
        reasons.append("missing_required_aspects")
        if avg_fitness < 0.45:
            reasons.append("low_authority_evidence")
    elif incidental_only and inject_heavy:
        level = "weak"
        reasons.append("incidental_or_injected_heavy")
    elif avg_fitness >= 0.35:
        level = "partial"
        reasons.append("moderate_authority_only")
    else:
        level = "weak"
        reasons.append("low_authority_evidence")

    if contradiction_count:
        reasons.append("unresolved_contradictions")
        if level == "sufficient":
            level = "partial"

    if budget_truncated:
        reasons.append("budget_truncation")

    if expected:
        reasons.append(f"expected_evidence_type={expected}")

    return EvidencePlanSufficiency(
        level=level,
        required_aspects_covered=covered_required,
        required_aspects_missing=missing_required,
        reasons=tuple(reasons),
        contradiction_count=contradiction_count,
        goal_satisfaction=round(goal, 4),
        expected_evidence_matched=expected_matched,
    )
