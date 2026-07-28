"""Language-layer speech-act rendering (RFC-100 Step 045).

Reasoning selects the act; this module maps typed instructions to
user-facing wording. No sufficiency/retrieval/memory logic here.
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
    """Deterministic body when skip_llm; None when LLM path continues."""
    qualify_suffix: str | None = None
    """Localized limitation sentence appended after LLM answer for qualify."""
    prompt_guidance: str | None = None
    """Concise typed guidance injected into the system prompt for qualify."""


_HINT_TO_INSTRUCTION: dict[str, LanguageInstruction] = {
    "answer_normally": "ANSWER",
    "qualify_due_to_incomplete_evidence": "QUALIFY_INCOMPLETE_EVIDENCE",
    "qualify_due_to_uncertain_sufficiency": "QUALIFY_INCOMPLETE_EVIDENCE",
    "ask_for_clarification": "CLARIFY_AMBIGUOUS_REQUEST",
    "refuse_due_to_missing_site_evidence": "REFUSE_INSUFFICIENT_SITE_EVIDENCE",
}

_CLARIFY = {
    "uk": "Уточніть, будь ласка, який саме аспект вас цікавить.",
    "en": "Please clarify which specific aspect you are interested in.",
}
_REFUSE = {
    "uk": "Я не знайшов достатньої інформації на сайті для надійної відповіді.",
    "en": "I could not find enough information on the site to provide a reliable answer.",
}
_QUALIFY = {
    "uk": (
        "На сайті знайдено релевантну інформацію, але доступні джерела "
        "можуть не містити повного переліку."
    ),
    "en": (
        "Relevant information was found on the site, but the available sources "
        "may not provide a complete list."
    ),
}
_QUALIFY_PROMPT = (
    "Language instruction QUALIFY_INCOMPLETE_EVIDENCE: answer from sources, "
    "then briefly note that site evidence may be incomplete (not that it is false)."
)


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
) -> SpeechActRenderPlan:
    """Build a Language render plan from a Reasoning speech-act decision."""
    lang = resolve_response_language(query_language, default_language)
    instruction = language_instruction_for(decision)
    act = decision.speech_act

    if act == "clarify":
        return SpeechActRenderPlan(
            speech_act=act,
            language_instruction=instruction,
            speech_act_reason=decision.speech_act_reason,
            deterministic=True,
            skip_llm=True,
            response_language=lang,
            text=_CLARIFY[lang],
        )
    if act == "refuse":
        return SpeechActRenderPlan(
            speech_act=act,
            language_instruction=instruction,
            speech_act_reason=decision.speech_act_reason,
            deterministic=True,
            skip_llm=True,
            response_language=lang,
            text=_REFUSE[lang],
        )
    if act == "qualify":
        return SpeechActRenderPlan(
            speech_act=act,
            language_instruction=instruction,
            speech_act_reason=decision.speech_act_reason,
            deterministic=False,
            skip_llm=False,
            response_language=lang,
            qualify_suffix=_QUALIFY[lang],
            prompt_guidance=_QUALIFY_PROMPT,
        )
    return SpeechActRenderPlan(
        speech_act="answer",
        language_instruction="ANSWER",
        speech_act_reason=decision.speech_act_reason,
        deterministic=False,
        skip_llm=False,
        response_language=lang,
    )


def apply_qualify_suffix(answer: str, suffix: str | None) -> str:
    """Append localized qualification when not already present."""
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
