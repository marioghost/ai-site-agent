"""Language-layer speech-act rendering (RFC-100 Step 045).

Reasoning selects the act; this module maps typed instructions.
User-facing wording comes from Settings (fallback_answer) or the admin
system prompt via LLM — not from hardcoded phrase tables.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.reasoning.speech_act import SpeechAct, SpeechActDecision

LanguageInstruction = Literal[
    "ANSWER",
    "QUALIFY_INCOMPLETE_EVIDENCE",
    "CLARIFY_AMBIGUOUS_REQUEST",
    "REFUSE_INSUFFICIENT_SITE_EVIDENCE",
]

ResponseLang = Literal["uk", "en"]


@dataclass(frozen=True)
class SpeechActRenderPlan:
    """How Language should produce the turn."""

    speech_act: SpeechAct
    language_instruction: LanguageInstruction
    speech_act_reason: str
    deterministic: bool
    skip_llm: bool
    response_language: ResponseLang
    text: str | None = None
    """Deterministic body when skip_llm (refuse → Settings.fallback_answer)."""
    qualify_suffix: str | None = None
    """Deprecated: always None — qualification is owned by the system prompt."""
    prompt_guidance: str | None = None
    """Typed Instruction code passed into CompactPromptBuilder (not prose)."""


_HINT_TO_INSTRUCTION: dict[str, LanguageInstruction] = {
    "answer_normally": "ANSWER",
    "qualify_due_to_incomplete_evidence": "QUALIFY_INCOMPLETE_EVIDENCE",
    "qualify_due_to_uncertain_sufficiency": "QUALIFY_INCOMPLETE_EVIDENCE",
    "ask_for_clarification": "CLARIFY_AMBIGUOUS_REQUEST",
    "refuse_due_to_missing_site_evidence": "REFUSE_INSUFFICIENT_SITE_EVIDENCE",
}


def resolve_response_language(query_language: str, default: str = "uk") -> ResponseLang:
    lang = (query_language or default or "uk").lower()
    if lang.startswith("en"):
        return "en"
    return "uk"


def language_instruction_for(decision: SpeechActDecision) -> LanguageInstruction:
    mapped = _HINT_TO_INSTRUCTION.get(decision.user_message_hint)
    if mapped:
        return mapped
    if decision.speech_act == "answer":
        return "ANSWER"
    if decision.speech_act == "qualify":
        return "QUALIFY_INCOMPLETE_EVIDENCE"
    if decision.speech_act == "clarify":
        return "CLARIFY_AMBIGUOUS_REQUEST"
    return "REFUSE_INSUFFICIENT_SITE_EVIDENCE"


def plan_speech_act_render(
    decision: SpeechActDecision,
    *,
    query_language: str,
    default_language: str = "uk",
    fallback_answer: str | None = None,
) -> SpeechActRenderPlan:
    """Build a Language render plan from a Reasoning speech-act decision.

    ``fallback_answer`` is Settings.fallback_answer (operator-owned wording).
    """
    lang = resolve_response_language(query_language, default_language)
    instruction = language_instruction_for(decision)
    act = decision.speech_act
    fallback = (fallback_answer or "").strip() or None

    if act == "refuse":
        return SpeechActRenderPlan(
            speech_act=act,
            language_instruction=instruction,
            speech_act_reason=decision.speech_act_reason,
            deterministic=True,
            skip_llm=True,
            response_language=lang,
            text=fallback,
        )
    if act == "clarify":
        # Wording owned by system prompt + LLM; typed Instruction only.
        return SpeechActRenderPlan(
            speech_act=act,
            language_instruction=instruction,
            speech_act_reason=decision.speech_act_reason,
            deterministic=False,
            skip_llm=False,
            response_language=lang,
            prompt_guidance=instruction,
        )
    if act == "qualify":
        return SpeechActRenderPlan(
            speech_act=act,
            language_instruction=instruction,
            speech_act_reason=decision.speech_act_reason,
            deterministic=False,
            skip_llm=False,
            response_language=lang,
            qualify_suffix=None,
            prompt_guidance=instruction,
        )
    return SpeechActRenderPlan(
        speech_act="answer",
        language_instruction="ANSWER",
        speech_act_reason=decision.speech_act_reason,
        deterministic=False,
        skip_llm=False,
        response_language=lang,
        prompt_guidance=None,
    )


def apply_qualify_suffix(answer: str, suffix: str | None) -> str:
    """No-op unless an explicit suffix is provided (legacy hook; unused)."""
    if not suffix:
        return answer
    body = (answer or "").rstrip()
    if not body:
        return suffix
    if suffix in body:
        return body
    return f"{body}\n\n{suffix}"


def speech_act_diagnostics(
    plan: SpeechActRenderPlan,
    *,
    decision: SpeechActDecision | None = None,
    assessment_diagnostics: dict | None = None,
    reasoning_path: str | None = None,
) -> dict:
    """Additive Language + Reasoning diagnostics for an activated render."""
    act_blob = (
        decision.to_diagnostics()
        if decision is not None
        else {
            "speech_act": plan.speech_act,
            "speech_act_reason": plan.speech_act_reason,
            "user_message_hint": plan.language_instruction,
            "qualification_required": plan.speech_act == "qualify",
            "clarification_required": plan.speech_act == "clarify",
            "refusal_required": plan.speech_act == "refuse",
            "clarification_question_hint": None,
            "refusal_reason": None,
        }
    )
    steps: list[dict] = [
        {
            "phase": "information_need_assessed",
            "status": "completed",
            "summary": "Information need classified from legacy intent/strategy signals.",
        },
        {
            "phase": "evidence_sufficiency_assessed",
            "status": "completed",
            "summary": "Sufficiency assessed from retrieval evidence (pre-LLM).",
        },
        {
            "phase": "speech_act_selected",
            "status": "completed",
            "summary": (
                f"Speech act={act_blob['speech_act']}; "
                f"reason={act_blob['speech_act_reason']}."
            ),
        },
        {
            "phase": "speech_act_rendered",
            "status": "completed",
            "summary": (
                f"Language instruction={plan.language_instruction}; "
                f"deterministic={plan.deterministic}; llm_skipped={plan.skip_llm}."
            ),
        },
    ]
    out: dict = {
        "speech_act": act_blob,
        "speech_act_reason": plan.speech_act_reason,
        "speech_act_applied": True,
        "language_instruction": plan.language_instruction,
        "deterministic_response_used": plan.deterministic,
        "llm_skipped": plan.skip_llm,
        "qualification_required": act_blob.get("qualification_required", False),
        "clarification_required": act_blob.get("clarification_required", False),
        "refusal_required": act_blob.get("refusal_required", False),
        "understanding_steps": steps,
    }
    if assessment_diagnostics is not None:
        out["evidence_sufficiency"] = assessment_diagnostics
    if reasoning_path is not None:
        out["reasoning_path"] = reasoning_path
    return out
