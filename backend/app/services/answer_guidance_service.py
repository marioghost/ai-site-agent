"""Evidence-aware answer guidance within the existing planner/generation path."""
from __future__ import annotations

import re

_SEGMENT_HINTS = {
    "business",
    "enterprise",
    "corporate",
    "retail",
    "student",
    "premium",
    "personal",
    "team",
    "clinic",
    "program",
    "version",
    "бізнес",
    "корпоратив",
    "преміум",
    "особист",
    "фоп",
}


def _extra_scope_hint(selected, focus_terms: set[str]) -> bool:
    blob = " ".join(
        f"{item.candidate.title} {item.candidate.heading} {item.candidate.text[:160]}"
        for item in selected
    ).lower()
    words = set(re.findall(r"[\w\u0400-\u04FF]{3,}", blob))
    return bool(words & _SEGMENT_HINTS) and not bool(focus_terms & _SEGMENT_HINTS)

def build_answer_guidance(
    *,
    planner_decision,
    evidence_plan,
) -> dict:
    answer_plan = planner_decision.answer_plan
    if evidence_plan is None:
        return {
            "answer_scope": "direct",
            "guidance_lines": [],
            "exact_match_count": 0,
            "category_support_count": 0,
            "adjacent_rejection_count": 0,
            "optional_slots_deferred": list(
                answer_plan.optional_slot_order[answer_plan.optional_slot_limit :]
            ),
            "required_slots": list(answer_plan.required_slot_order),
            "output_budget_words": answer_plan.target_words,
            "output_budget_sentences": answer_plan.target_sentences,
        }

    labels = [item.candidate.compatibility_label for item in evidence_plan.selected]
    focus_terms = {
        str(term).lower()
        for term in getattr(planner_decision.understanding, "focus_terms", []) or []
    }
    exact = sum(
        label
        in {
            "exact_match",
            "same_product",
            "organization_support",
            "navigation_support",
            "definition_support",
            "procedure_support",
        }
        for label in labels
    )
    category = sum(label in {"category_support", "same_category", "supporting_evidence"} for label in labels)
    historical = sum(label == "historical" for label in labels)
    ambiguous = sum(label == "ambiguous" for label in labels)
    adjacent_rejected = [
        item.to_dict()
        for item in evidence_plan.rejected
        if item.candidate.compatibility_label
        in {"adjacent_incompatible", "news_only", "marketing_only", "historical"}
    ][:8]

    understanding = planner_decision.understanding
    scope = "direct"
    guidance_lines: list[str] = []
    if answer_plan.answer_type in {"fact", "definition", "general", "listing", "comparison"}:
        if exact == 0 and (category > 0 or historical > 0):
            scope = "qualified"
            guidance_lines.append(
                "State the exact scope supported by the evidence. If the evidence applies "
                "only to one variant, segment, audience, currency, duration, or version, "
                "name that scope and do not generalize."
            )
        elif exact == 0 and ambiguous > 0:
            scope = "partial"
            guidance_lines.append(
                "Answer only the part that is directly supported. If the exact subject "
                "is still unclear, say what the evidence does cover."
            )
        elif _extra_scope_hint(evidence_plan.selected, focus_terms):
            scope = "qualified"
            guidance_lines.append(
                "The evidence appears scoped to a narrower segment or variant. Name that "
                "scope explicitly and do not present it as universal."
            )
    if answer_plan.answer_type == "contact" or getattr(understanding, "semantic_focus", "") == "locator":
        guidance_lines.append(
            "Give actionable navigation or steps from the evidence, not a generic referral to the site."
        )
    if adjacent_rejected:
        guidance_lines.append(
            "Ignore adjacent but different products, categories, or incidental pages that do not answer the same question."
        )

    sufficiency = getattr(evidence_plan, "sufficiency", None)
    if sufficiency is not None:
        level = getattr(sufficiency, "level", "") or ""
        goal = float(getattr(sufficiency, "goal_satisfaction", 1.0) or 0.0)
        matched = bool(getattr(sufficiency, "expected_evidence_matched", True))
        if (
            level in {"weak", "no_evidence"}
            or (not matched and goal < 0.35)
            or not evidence_plan.selected
        ):
            scope = "refuse"
            guidance_lines = [
                "The selected evidence does not answer this question. Clearly say you cannot "
                "answer from the available site materials. Do not invent facts, contacts, "
                "rates, or procedures."
            ] + guidance_lines

    return {
        "answer_scope": scope,
        "guidance_lines": guidance_lines,
        "exact_match_count": exact,
        "category_support_count": category,
        "adjacent_rejection_count": len(adjacent_rejected),
        "rejected_adjacent_sources": adjacent_rejected,
        "optional_slots_deferred": list(
            answer_plan.optional_slot_order[answer_plan.optional_slot_limit :]
        ),
        "required_slots": list(answer_plan.required_slot_order),
        "output_budget_words": answer_plan.target_words,
        "output_budget_sentences": answer_plan.target_sentences,
        "semantic_focus": getattr(understanding, "semantic_focus", None),
        "expected_evidence_type": getattr(understanding, "expected_evidence_type", None),
        "goal_satisfaction": getattr(sufficiency, "goal_satisfaction", None) if sufficiency else None,
        "expected_evidence_matched": getattr(sufficiency, "expected_evidence_matched", None)
        if sufficiency
        else None,
    }
