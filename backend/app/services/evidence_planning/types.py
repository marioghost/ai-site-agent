"""Normalized evidence planning types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.qdrant_service import SearchHit
from app.services.rag_planning.contracts import KnowledgePlan

SufficiencyLevel = Literal["sufficient", "partial", "weak", "no_evidence"]


@dataclass
class EvidenceCandidate:
    candidate_id: str
    source_id: int
    chunk_index: int
    url: str
    title: str
    heading: str
    text: str
    document_type: str
    page_role: str
    source_purpose: str
    language: str
    dense_score: float = 0.0
    lexical_score: float = 0.0
    rerank_score: float = 0.0
    naturally_retrieved: bool = True
    broad_injected: bool = False
    inject_reason: str = ""
    canonical: bool = False
    kp_preferred: bool = False
    kp_deprioritized: bool = False
    quality_score: float = 0.5
    answerability: float = 0.5
    intent_compatibility: float = 0.5
    focus_match_score: float = 0.0
    authority_fitness: float = 0.0
    compatibility_label: str = "ambiguous"
    fitness_factors: dict[str, float] = field(default_factory=dict)
    fitness_band: str = "general"
    duplicate_group: str = ""
    available_aspects: frozenset[str] = frozenset()
    forbidden_for_query: bool = False
    section_text: str = ""
    section_heading: str = ""
    section_relevance: float = 0.0
    token_estimate: int = 0
    raw_hit: SearchHit | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_id": self.source_id,
            "chunk_index": self.chunk_index,
            "url": self.url,
            "title": self.title,
            "document_type": self.document_type,
            "page_role": self.page_role,
            "source_purpose": self.source_purpose,
            "language": self.language,
            "rerank_score": round(self.rerank_score, 4),
            "naturally_retrieved": self.naturally_retrieved,
            "broad_injected": self.broad_injected,
            "inject_reason": self.inject_reason,
            "focus_match_score": round(self.focus_match_score, 4),
            "authority_fitness": round(self.authority_fitness, 4),
            "compatibility_label": self.compatibility_label,
            "fitness_band": self.fitness_band,
            "fitness_factors": self.fitness_factors,
            "duplicate_group": self.duplicate_group,
            "available_aspects": sorted(self.available_aspects),
            "section_relevance": round(self.section_relevance, 4),
            "token_estimate": self.token_estimate,
        }


@dataclass
class SelectedEvidence:
    candidate: EvidenceCandidate
    aspects_new: tuple[str, ...]
    aspects_covered: tuple[str, ...]
    marginal_value: float
    selection_reason: str
    final_order: int

    def to_dict(self) -> dict[str, Any]:
        out = self.candidate.to_dict()
        out.update(
            {
                "aspects_new": list(self.aspects_new),
                "aspects_covered": list(self.aspects_covered),
                "marginal_value": round(self.marginal_value, 4),
                "selection_reason": self.selection_reason,
                "final_order": self.final_order,
                "status": "selected",
            }
        )
        return out


@dataclass
class RejectedEvidence:
    candidate: EvidenceCandidate
    rejection_reason: str

    def to_dict(self) -> dict[str, Any]:
        out = self.candidate.to_dict()
        out.update({"rejection_reason": self.rejection_reason, "status": "rejected"})
        return out


@dataclass
class EvidencePlanSufficiency:
    level: SufficiencyLevel
    required_aspects_covered: tuple[str, ...]
    required_aspects_missing: tuple[str, ...]
    reasons: tuple[str, ...] = ()
    contradiction_count: int = 0
    goal_satisfaction: float = 0.0
    expected_evidence_matched: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "required_aspects_covered": list(self.required_aspects_covered),
            "required_aspects_missing": list(self.required_aspects_missing),
            "reasons": list(self.reasons),
            "contradiction_count": self.contradiction_count,
            "goal_satisfaction": round(self.goal_satisfaction, 4),
            "expected_evidence_matched": self.expected_evidence_matched,
        }


@dataclass
class EvidencePlan:
    intent: str
    knowledge_plan: KnowledgePlan
    selected: list[SelectedEvidence]
    rejected: list[RejectedEvidence]
    sufficiency: EvidencePlanSufficiency
    contradictions: list[dict[str, Any]]
    packing_decisions: list[dict[str, Any]]
    candidate_count: int
    plan_ms: int = 0
    ordered_hits: list[SearchHit] = field(default_factory=list)

    def to_diagnostics(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "knowledge_plan": self.knowledge_plan.to_dict(),
            "semantic_focus": getattr(self.knowledge_plan, "semantic_focus", None),
            "expected_evidence_type": getattr(
                self.knowledge_plan, "expected_evidence_type", None
            ),
            "candidate_count": self.candidate_count,
            "selected_count": len(self.selected),
            "rejected_count": len(self.rejected),
            "selected": [s.to_dict() for s in self.selected],
            "rejected": [r.to_dict() for r in self.rejected],
            "sufficiency": self.sufficiency.to_dict(),
            "contradictions": self.contradictions,
            "packing_decisions": self.packing_decisions,
            "plan_ms": self.plan_ms,
            "final_order_urls": [s.candidate.url for s in self.selected],
        }
