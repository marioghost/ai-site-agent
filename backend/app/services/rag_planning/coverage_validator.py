"""Deterministic coverage validation — no LLM."""
from __future__ import annotations

import re

from app.services.evidence_planning.types import EvidencePlan, SelectedEvidence
from app.services.rag_planning.contracts import (
    AnswerCoverageReport,
    CoverageSnapshot,
    EvidenceCoverageReport,
    KnowledgeCoverageReport,
    KnowledgePlan,
    PipelineDecisionRecord,
    RetrievalCoverageReport,
)
from app.services.rag_planning.purpose_catalog import SLOT_COVERAGE_HINTS
from app.services.retrieval_engine.types import RetrievalQualityMetrics


class AnswerCoverageValidator:
    """Deterministic coverage assessment — single owner for all coverage stages."""

    @staticmethod
    def validate_knowledge_coverage(
        selected: list[SelectedEvidence],
        knowledge_plan: KnowledgePlan,
    ) -> KnowledgeCoverageReport:
        covered: set[str] = set()
        for item in selected:
            covered |= set(item.aspects_new)
            covered |= item.candidate.available_aspects

        required = set(knowledge_plan.required_slots)
        covered_required = tuple(sorted(required & covered))
        missing = tuple(sorted(required - covered))
        pct = 1.0 if not required else len(covered_required) / len(required)
        reasons: list[str] = []
        if missing:
            reasons.append("missing_required_knowledge_slots")
        else:
            reasons.append("required_knowledge_slots_covered")
        return KnowledgeCoverageReport(
            required_covered=covered_required,
            required_missing=missing,
            coverage_pct=pct,
            reasons=tuple(reasons),
        )

    @staticmethod
    def validate_retrieval_coverage(
        metrics: RetrievalQualityMetrics | None,
    ) -> RetrievalCoverageReport | None:
        if metrics is None or not metrics.documents_found:
            return None
        selected = metrics.documents_after_reranking or 0
        avg = metrics.avg_final_score if metrics.avg_final_score else None
        reasons: list[str] = []
        if selected:
            reasons.append("retrieval_documents_selected")
        else:
            reasons.append("no_documents_selected")
        return RetrievalCoverageReport(
            documents_found=metrics.documents_found,
            documents_selected=selected,
            avg_score=avg,
            reasons=tuple(reasons),
        )

    @staticmethod
    def validate_evidence_coverage(evidence_plan: EvidencePlan) -> EvidenceCoverageReport:
        level = evidence_plan.sufficiency.level
        reasons = list(evidence_plan.sufficiency.reasons) or ["evidence_plan_assessed"]
        return EvidenceCoverageReport(level=level, reasons=tuple(reasons))

    @staticmethod
    def validate_answer_coverage(
        answer_text: str,
        *,
        selected: list[SelectedEvidence],
        knowledge_plan: KnowledgePlan,
    ) -> AnswerCoverageReport:
        if not answer_text.strip():
            return AnswerCoverageReport(
                slot_status={s: "missing" for s in knowledge_plan.required_slots},
                coverage_pct=0.0,
                reasons=("empty_answer",),
            )

        answer_lower = answer_text.lower()
        evidence_tokens: set[str] = set()
        for item in selected:
            text = (item.candidate.section_text or item.candidate.text).lower()
            evidence_tokens.update(_tokens(text))

        slot_status: dict[str, str] = {}
        for slot in knowledge_plan.required_slots:
            slot_status[slot] = _slot_status(slot, answer_lower, evidence_tokens)

        covered_count = sum(1 for s in slot_status.values() if s == "covered")
        required_count = len(knowledge_plan.required_slots)
        pct = 1.0 if not required_count else covered_count / required_count
        reasons: list[str] = []
        if pct >= 1.0:
            reasons.append("answer_covers_required_slots")
        elif pct >= 0.5:
            reasons.append("partial_answer_slot_coverage")
        else:
            reasons.append("weak_answer_slot_coverage")

        return AnswerCoverageReport(
            slot_status=slot_status,
            coverage_pct=pct,
            reasons=tuple(reasons),
        )

    @classmethod
    def build_snapshot(
        cls,
        *,
        evidence_plan: EvidencePlan,
        knowledge_plan: KnowledgePlan,
        answer_text: str = "",
        retrieval_quality: RetrievalQualityMetrics | None = None,
    ) -> CoverageSnapshot:
        knowledge = cls.validate_knowledge_coverage(evidence_plan.selected, knowledge_plan)
        evidence = cls.validate_evidence_coverage(evidence_plan)
        retrieval = cls.validate_retrieval_coverage(retrieval_quality)
        answer = None
        if answer_text:
            answer = cls.validate_answer_coverage(
                answer_text,
                selected=evidence_plan.selected,
                knowledge_plan=knowledge_plan,
            )
        return CoverageSnapshot(
            knowledge=knowledge,
            evidence=evidence,
            retrieval=retrieval,
            answer=answer,
        )

    @staticmethod
    def decision_records(snapshot: CoverageSnapshot) -> tuple[PipelineDecisionRecord, ...]:
        records: list[PipelineDecisionRecord] = []
        if snapshot.retrieval is not None:
            records.append(
                PipelineDecisionRecord(
                    stage="retrieval_coverage",
                    owner="AnswerCoverageValidator",
                    action="assessed",
                    reason=snapshot.retrieval.reasons[0] if snapshot.retrieval.reasons else "assessed",
                    metadata=snapshot.retrieval.to_dict(),
                )
            )
        records.extend(
            [
                PipelineDecisionRecord(
                    stage="knowledge_coverage",
                    owner="AnswerCoverageValidator",
                    action="assessed",
                    reason=snapshot.knowledge.reasons[0] if snapshot.knowledge.reasons else "assessed",
                    metadata=snapshot.knowledge.to_dict(),
                ),
                PipelineDecisionRecord(
                    stage="evidence_coverage",
                    owner="AnswerCoverageValidator",
                    action="assessed",
                    reason=snapshot.evidence.reasons[0] if snapshot.evidence.reasons else "assessed",
                    metadata=snapshot.evidence.to_dict(),
                ),
            ]
        )
        if snapshot.answer is not None:
            records.append(
                PipelineDecisionRecord(
                    stage="answer_coverage",
                    owner="AnswerCoverageValidator",
                    action="assessed",
                    reason=snapshot.answer.reasons[0] if snapshot.answer.reasons else "assessed",
                    metadata=snapshot.answer.to_dict(),
                )
            )
        return tuple(records)


# Module-level aliases for backward compatibility.
validate_knowledge_coverage = AnswerCoverageValidator.validate_knowledge_coverage
validate_evidence_coverage = AnswerCoverageValidator.validate_evidence_coverage
validate_answer_coverage = AnswerCoverageValidator.validate_answer_coverage
build_coverage_snapshot = AnswerCoverageValidator.build_snapshot
coverage_decision_records = AnswerCoverageValidator.decision_records


def _slot_status(slot: str, answer_lower: str, evidence_tokens: set[str]) -> str:
    hints = SLOT_COVERAGE_HINTS.get(slot, (slot.replace("_", " "),))
    if not hints or hints == ("",):
        return "unknown"
    answer_hit = any(h in answer_lower for h in hints if h)
    evidence_hit = any(h in " ".join(evidence_tokens) for h in hints if h)
    if answer_hit and evidence_hit:
        return "covered"
    if evidence_hit and not answer_hit:
        return "missing_in_answer"
    if answer_hit:
        return "unknown"
    return "missing"


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[\w\u0400-\u04FF]{3,}", text.lower())}
