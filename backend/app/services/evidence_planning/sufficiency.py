"""Pre-LLM evidence sufficiency from the evidence plan."""
from __future__ import annotations

from app.services.evidence_planning.types import (
    EvidencePlanSufficiency,
    SelectedEvidence,
    SufficiencyLevel,
)
from app.services.rag_planning.contracts import KnowledgePlan


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

    reasons: list[str] = []
    level: SufficiencyLevel

    if not missing_required and avg_fitness >= 0.42:
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

    return EvidencePlanSufficiency(
        level=level,
        required_aspects_covered=covered_required,
        required_aspects_missing=missing_required,
        reasons=tuple(reasons),
        contradiction_count=contradiction_count,
    )
