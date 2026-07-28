"""Speech-act selection (RFC-100 Step 044 / activated in Step 045).

Source-scoped decision from evidence sufficiency — not world-truth judgment.
Reasoning owns selection; Language owns wording when
REASONING_SPEECH_ACTS_ENABLED is on (and Reasoning is on the path).

Deterministic, in-memory, no retrieval / LLM / Epistemic Memory.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.reasoning.evidence_sufficiency import EvidenceSufficiencyAssessment

SpeechAct = Literal["answer", "qualify", "clarify", "refuse"]

_AMBIGUOUS_REASONS = frozenset(
    {
        "ambiguous_or_clarification_need",
    }
)
_REFUSE_REASONS = frozenset(
    {
        "no_selected_evidence",
        "context_not_used",
        "missing_source_provenance",
    }
)


@dataclass(frozen=True)
class SpeechActDecision:
    """Typed speech-act contract — Reasoning owns the act; Language owns wording."""

    speech_act: SpeechAct
    speech_act_reason: str
    user_message_hint: str
    qualification_required: bool = False
    clarification_question_hint: str | None = None
    refusal_reason: str | None = None

    @property
    def clarification_required(self) -> bool:
        return self.speech_act == "clarify"

    @property
    def refusal_required(self) -> bool:
        return self.speech_act == "refuse"

    def to_diagnostics(self) -> dict[str, Any]:
        return {
            "speech_act": self.speech_act,
            "speech_act_reason": self.speech_act_reason,
            "user_message_hint": self.user_message_hint,
            "qualification_required": self.qualification_required,
            "clarification_required": self.clarification_required,
            "refusal_required": self.refusal_required,
            "clarification_question_hint": self.clarification_question_hint,
            "refusal_reason": self.refusal_reason,
        }


def select_speech_act(
    assessment: EvidenceSufficiencyAssessment,
    *,
    information_need: str | None = None,
) -> SpeechActDecision:
    """Map sufficiency (+ need signals already inside assessment) to a speech act.

    Conservative v1:
    - refuse when site evidence is unusable;
    - clarify when the need is ambiguous;
    - qualify when completeness is uncertain or sufficiency is unknown;
    - answer only when sufficiency is asserted for a scoped need.
    """
    reasons = set(assessment.sufficiency_reasons)
    need = (information_need or "").strip().lower()

    # 4 / 6 — no usable evidence or invalid provenance
    if assessment.sufficiency_status == "insufficient" or (
        reasons & _REFUSE_REASONS
    ):
        detail = (
            assessment.missing_evidence_hint
            or "Insufficient website evidence to support a grounded response."
        )
        reason_code = next(
            (r for r in assessment.sufficiency_reasons if r in _REFUSE_REASONS),
            "insufficient_site_evidence",
        )
        return SpeechActDecision(
            speech_act="refuse",
            speech_act_reason=reason_code,
            user_message_hint="refuse_due_to_missing_site_evidence",
            refusal_reason=detail,
        )

    # 3 — ambiguous / underspecified request
    if reasons & _AMBIGUOUS_REASONS or "clarif" in need or "ambigu" in need:
        return SpeechActDecision(
            speech_act="clarify",
            speech_act_reason="ambiguous_or_underspecified_need",
            user_message_hint="ask_for_clarification",
            clarification_question_hint=(
                "Ask which specific aspect of the site the user needs."
            ),
        )

    # 2 / 6 — enumeration or completeness risk
    if assessment.completeness_risk:
        return SpeechActDecision(
            speech_act="qualify",
            speech_act_reason="completeness_risk",
            user_message_hint="qualify_due_to_incomplete_evidence",
            qualification_required=True,
        )

    # 1 — asserted sufficient for narrow scoped answer
    if (
        assessment.sufficiency_status == "sufficient"
        and assessment.evidence_sufficient is True
    ):
        return SpeechActDecision(
            speech_act="answer",
            speech_act_reason="sufficient_scoped_evidence",
            user_message_hint="answer_normally",
        )

    # 5 — unknown sufficiency but some evidence exists → qualify (not false certainty)
    if assessment.evidence_count > 0:
        return SpeechActDecision(
            speech_act="qualify",
            speech_act_reason="sufficiency_unknown_with_evidence",
            user_message_hint="qualify_due_to_uncertain_sufficiency",
            qualification_required=True,
        )

    # Defensive fallback — treat as refuse (no usable path)
    return SpeechActDecision(
        speech_act="refuse",
        speech_act_reason="no_usable_evidence_path",
        user_message_hint="refuse_due_to_missing_site_evidence",
        refusal_reason="No usable website evidence path for this turn.",
    )
