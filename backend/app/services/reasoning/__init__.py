"""Reasoning subsystem — RFC-100 Steps 039–048."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.reasoning.evidence_sufficiency import EvidenceSufficiencyAssessment
    from app.services.reasoning.reasoning_service import ReasoningService
    from app.services.reasoning.speech_act import SpeechActDecision
    from app.services.reasoning.types import (
        REASONING_PATH_LEGACY,
        REASONING_PATH_SERVICE,
        ReasoningRequest,
        ReasoningResult,
    )

__all__ = [
    "REASONING_PATH_LEGACY",
    "REASONING_PATH_SERVICE",
    "EvidenceSufficiencyAssessment",
    "ReasoningRequest",
    "ReasoningResult",
    "ReasoningService",
    "SpeechActDecision",
    "assess_evidence_sufficiency",
    "select_speech_act",
]


def __getattr__(name: str):
    if name in ("REASONING_PATH_LEGACY", "REASONING_PATH_SERVICE", "ReasoningRequest", "ReasoningResult"):
        from app.services.reasoning.types import (
            REASONING_PATH_LEGACY,
            REASONING_PATH_SERVICE,
            ReasoningRequest,
            ReasoningResult,
        )

        return {
            "REASONING_PATH_LEGACY": REASONING_PATH_LEGACY,
            "REASONING_PATH_SERVICE": REASONING_PATH_SERVICE,
            "ReasoningRequest": ReasoningRequest,
            "ReasoningResult": ReasoningResult,
        }[name]
    if name == "ReasoningService":
        from app.services.reasoning.reasoning_service import ReasoningService

        return ReasoningService
    if name == "EvidenceSufficiencyAssessment":
        from app.services.reasoning.evidence_sufficiency import EvidenceSufficiencyAssessment

        return EvidenceSufficiencyAssessment
    if name == "assess_evidence_sufficiency":
        from app.services.reasoning.evidence_sufficiency import assess_evidence_sufficiency

        return assess_evidence_sufficiency
    if name == "SpeechActDecision":
        from app.services.reasoning.speech_act import SpeechActDecision

        return SpeechActDecision
    if name == "select_speech_act":
        from app.services.reasoning.speech_act import select_speech_act

        return select_speech_act
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
