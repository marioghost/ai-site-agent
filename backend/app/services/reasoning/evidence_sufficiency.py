"""Evidence sufficiency assessment (RFC-100 Step 043).

Source-scoped advisory judgment: does available website evidence appear
sufficient for the requested response? Not world-truth confidence.

In-memory, deterministic, no retrieval or LLM calls.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from app.services.rag_service import RagResult, RagSource
from app.services.reasoning.memory_assist_types import MemoryAssistResult
from app.services.reasoning.memory_canonical_shadow_types import MemoryCanonicalShadowResult

SufficiencyStatus = Literal["sufficient", "insufficient", "unknown"]

# Legacy intents / strategies that imply enumeration without completeness proof.
_ENUMERATION_INTENTS = frozenset(
    {
        "category_overview",
        "list",
        "products",
        "services",
    }
)
_ENUMERATION_STRATEGIES = frozenset({"list"})

# Ambiguity / clarification — cannot claim sufficiency.
_AMBIGUOUS_INTENTS = frozenset(
    {
        "unknown",
        "clarification",
        "ambiguous",
        "ambiguity",
    }
)

# Narrow factual-ish intents where selected evidence can support a scoped answer.
_NARROW_FACTUAL_INTENTS = frozenset(
    {
        "specific_fact",
        "fact",
        "contacts_query",
        "contact",
        "pricing",
        "policy",
        "process",
        "hours",
    }
)


@dataclass(frozen=True)
class EvidenceSufficiencyAssessment:
    """Typed sufficiency outcome — advisory only in Step 043."""

    evidence_sufficient: bool | None
    sufficiency_status: SufficiencyStatus
    sufficiency_reasons: tuple[str, ...] = ()
    evidence_count: int = 0
    independent_source_count: int | None = None
    completeness_risk: bool = False
    missing_evidence_hint: str | None = None

    def to_diagnostics(self) -> dict[str, Any]:
        return {
            "status": self.sufficiency_status,
            "evidence_sufficient": self.evidence_sufficient,
            "reasons": list(self.sufficiency_reasons),
            "evidence_count": self.evidence_count,
            "independent_source_count": self.independent_source_count,
            "completeness_risk": self.completeness_risk,
            "missing_evidence_hint": self.missing_evidence_hint,
        }


def _source_key(src: RagSource) -> str:
    url = (src.url or "").strip()
    if url:
        return f"url:{url}"
    title = (src.title or "").strip()
    if title:
        return f"title:{title}"
    return f"anon:{id(src)}"


def _count_evidence(sources: list[RagSource]) -> tuple[int, int]:
    """Return (evidence_count, independent_source_count).

    Evidence count = number of citation entries.
    Independent sources = distinct URLs (or titles if URL empty).
    Duplicate URLs count once for independence.
    """
    evidence_count = len(sources)
    keys = {_source_key(s) for s in sources}
    return evidence_count, len(keys)


def _has_valid_provenance(sources: list[RagSource]) -> bool:
    if not sources:
        return False
    return all(bool((s.url or "").strip()) for s in sources)


def _answer_strategy(result: RagResult) -> str:
    cfg = result.applied_knowledge_config
    if isinstance(cfg, dict):
        return str(cfg.get("answer_strategy") or "generic").lower()
    return "generic"


def _is_enumeration(intent: str, strategy: str) -> bool:
    intent_l = (intent or "").lower()
    strategy_l = (strategy or "").lower()
    if strategy_l in _ENUMERATION_STRATEGIES:
        return True
    if intent_l in _ENUMERATION_INTENTS:
        return True
    if "list" in intent_l or "enumeration" in intent_l:
        return True
    # Broad overview needs — completeness not proven by selected hits alone.
    if intent_l in {
        "entity_overview",
        "topic_overview",
        "category_overview",
        "overview",
    }:
        return True
    return False


def _is_ambiguous(intent: str, used_context: bool, sources: list[RagSource]) -> bool:
    intent_l = (intent or "").lower()
    if intent_l in _AMBIGUOUS_INTENTS:
        return True
    if "clarif" in intent_l or "ambigu" in intent_l:
        return True
    # Clarification-style answers without grounding often signal need ambiguity.
    return False


def assess_evidence_sufficiency(result: RagResult) -> EvidenceSufficiencyAssessment:
    """Assess whether available website evidence appears sufficient.

    Conservative v1 rules — unknown preferred over false precision.
    Does not mutate ``result`` or call retrieval/LLM.
    """
    sources = list(result.sources or [])
    evidence_count, independent_count = _count_evidence(sources)
    intent = (result.query_intent or "unknown").strip() or "unknown"
    strategy = _answer_strategy(result)
    used_context = bool(result.used_context)

    # --- Hard insufficient ---
    if evidence_count == 0 or not used_context:
        return EvidenceSufficiencyAssessment(
            evidence_sufficient=False,
            sufficiency_status="insufficient",
            sufficiency_reasons=(
                "no_selected_evidence" if evidence_count == 0 else "context_not_used",
            ),
            evidence_count=evidence_count,
            independent_source_count=independent_count if evidence_count else 0,
            completeness_risk=False,
            missing_evidence_hint="No website evidence was selected for this turn.",
        )

    if not _has_valid_provenance(sources):
        return EvidenceSufficiencyAssessment(
            evidence_sufficient=False,
            sufficiency_status="insufficient",
            sufficiency_reasons=("missing_source_provenance",),
            evidence_count=evidence_count,
            independent_source_count=independent_count,
            completeness_risk=False,
            missing_evidence_hint="Selected evidence lacks valid source URLs.",
        )

    # --- Ambiguous / clarification need ---
    if _is_ambiguous(intent, used_context, sources):
        return EvidenceSufficiencyAssessment(
            evidence_sufficient=None,
            sufficiency_status="unknown",
            sufficiency_reasons=("ambiguous_or_clarification_need",),
            evidence_count=evidence_count,
            independent_source_count=independent_count,
            completeness_risk=False,
            missing_evidence_hint="Information need is ambiguous; sufficiency not asserted.",
        )

    # --- Enumeration / list completeness risk ---
    if _is_enumeration(intent, strategy):
        return EvidenceSufficiencyAssessment(
            evidence_sufficient=None,
            sufficiency_status="unknown",
            sufficiency_reasons=(
                "enumeration_without_completeness_signal",
                "completeness_not_proven",
            ),
            evidence_count=evidence_count,
            independent_source_count=independent_count,
            completeness_risk=True,
            missing_evidence_hint=(
                "List/enumeration requests lack a completeness signal from the site."
            ),
        )

    # --- Narrow factual with valid evidence ---
    intent_l = intent.lower()
    if intent_l in _NARROW_FACTUAL_INTENTS or strategy in {"generic", "fact", "direct"}:
        # Presence of grounded sources is advisory "sufficient" for scoped site answers —
        # not a claim of world truth or exhaustive coverage.
        return EvidenceSufficiencyAssessment(
            evidence_sufficient=True,
            sufficiency_status="sufficient",
            sufficiency_reasons=("selected_evidence_with_provenance",),
            evidence_count=evidence_count,
            independent_source_count=independent_count,
            completeness_risk=False,
            missing_evidence_hint=None,
        )

    # Default: evidence present but need shape unclear → unknown
    return EvidenceSufficiencyAssessment(
        evidence_sufficient=None,
        sufficiency_status="unknown",
        sufficiency_reasons=("information_need_shape_unclear",),
        evidence_count=evidence_count,
        independent_source_count=independent_count,
        completeness_risk=False,
        missing_evidence_hint="Need type is unclear; sufficiency left unknown.",
    )


def enrich_assessment_with_memory_assist(
    assessment: EvidenceSufficiencyAssessment,
    memory_assist: MemoryAssistResult | dict[str, object] | None,
) -> EvidenceSufficiencyAssessment:
    """Advisory enrichment only — never downgrade strong retrieval sufficiency."""
    if memory_assist is None:
        return assessment
    usable = False
    if isinstance(memory_assist, dict):
        usable = bool(memory_assist.get("memory_usable_for_evidence"))
    else:
        usable = bool(getattr(memory_assist, "usable_for_evidence", False))
    if not usable:
        return assessment

    retrieval_weak = (
        assessment.evidence_sufficient is False
        or assessment.completeness_risk
        or assessment.sufficiency_status == "unknown"
    )
    if not retrieval_weak:
        return assessment

    hint = (
        "Memory reports supporting observations that are not reflected in "
        "selected retrieval evidence."
    )
    reasons = assessment.sufficiency_reasons + ("memory_support_not_in_retrieval",)
    return EvidenceSufficiencyAssessment(
        evidence_sufficient=assessment.evidence_sufficient,
        sufficiency_status=assessment.sufficiency_status,
        sufficiency_reasons=reasons,
        evidence_count=assessment.evidence_count,
        independent_source_count=assessment.independent_source_count,
        completeness_risk=True,
        missing_evidence_hint=hint,
    )


def build_reasoning_diagnostics(
    assessment: EvidenceSufficiencyAssessment,
    *,
    reasoning_path: str,
    speech_act: Any | None = None,
    memory_assist: MemoryAssistResult | dict[str, object] | None = None,
    canonical_shadow: MemoryCanonicalShadowResult | dict[str, object] | None = None,
) -> dict[str, Any]:
    """Additive diagnostics — decision summaries only, no chain-of-thought."""
    steps: list[dict[str, Any]] = [
        {
            "phase": "information_need_assessed",
            "status": "completed",
            "summary": "Information need classified from legacy intent/strategy signals.",
        },
        {
            "phase": "evidence_sufficiency_assessed",
            "status": "completed",
            "summary": (
                f"Sufficiency={assessment.sufficiency_status}; "
                f"evidence_count={assessment.evidence_count}; "
                f"completeness_risk={assessment.completeness_risk}."
            ),
        },
    ]
    diagnostics: dict[str, Any] = {
        "reasoning_path": reasoning_path,
        "evidence_sufficiency": assessment.to_diagnostics(),
        "understanding_steps": steps,
    }
    if speech_act is not None:
        act_diag = speech_act.to_diagnostics()
        diagnostics["speech_act"] = act_diag
        diagnostics["speech_act_reason"] = act_diag["speech_act_reason"]
        diagnostics["qualification_required"] = act_diag["qualification_required"]
        diagnostics["clarification_required"] = act_diag["clarification_required"]
        diagnostics["refusal_required"] = act_diag["refusal_required"]
        steps.append(
            {
                "phase": "speech_act_selected",
                "status": "completed",
                "summary": (
                    f"Speech act={act_diag['speech_act']}; "
                    f"reason={act_diag['speech_act_reason']} "
                    "(advisory; Language owns wording)."
                ),
            }
        )
    if memory_assist is not None:
        if hasattr(memory_assist, "to_diagnostics"):
            diagnostics["memory_assist"] = memory_assist.to_diagnostics()
        elif isinstance(memory_assist, dict):
            diagnostics["memory_assist"] = memory_assist
    if canonical_shadow is not None:
        if hasattr(canonical_shadow, "to_diagnostics"):
            diagnostics["memory_canonical_shadow"] = canonical_shadow.to_diagnostics()
        elif isinstance(canonical_shadow, dict):
            diagnostics["memory_canonical_shadow"] = canonical_shadow
    return diagnostics


def assessment_as_dict(assessment: EvidenceSufficiencyAssessment) -> dict[str, Any]:
    data = asdict(assessment)
    data["sufficiency_reasons"] = list(assessment.sufficiency_reasons)
    return data
