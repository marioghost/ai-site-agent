"""Evidence planner — single decision owner for final context selection."""
from __future__ import annotations

from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.settings import Settings
from app.models.source import Source
from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.evidence_planning.authority import evaluate_authority_fitness
from app.services.evidence_planning.contradiction import detect_contradictions
from app.services.evidence_planning.coverage import select_by_coverage
from app.services.evidence_planning.diversity import dedupe_language_candidates
from app.services.evidence_planning.normalizer import normalize_hits
from app.services.evidence_planning.packer import pack_selected_evidence
from app.services.evidence_planning.sections import apply_section_selection
from app.services.evidence_planning.sufficiency import assess_plan_sufficiency
from app.services.evidence_planning.types import EvidencePlan
from app.services.llm_mode_service import effective_generation_settings
from app.services.qdrant_service import SearchHit
from app.services.rag_planning.contracts import PlannerDecision


class EvidencePlanner:
    """Plan final evidence selection from retrieval candidates."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def plan(
        self,
        hits: list[SearchHit],
        *,
        planner_decision: PlannerDecision,
        profile: KnowledgeProfile | None,
        query: str,
        query_language: str,
        settings: Settings,
        system_prompt: str = "",
        user_message: str = "",
        document_scores: dict[int, float] | None = None,
    ) -> EvidencePlan:
        t0 = perf_counter()
        knowledge_plan = planner_decision.knowledge_plan
        understanding = planner_decision.understanding
        intent = planner_decision.information_need

        candidates = normalize_hits(
            hits,
            intent=intent,
            profile=profile,
            query_language=query_language,
            document_scores=document_scores,
        )
        candidates, lang_excluded = dedupe_language_candidates(candidates, query_language)

        source_meta = self._load_sources({c.source_id for c in candidates})
        eff = effective_generation_settings(settings)
        max_sources = int(eff.get("max_sources_in_prompt") or getattr(settings, "max_sources_in_prompt", 3) or 3)
        max_chunks = int(getattr(settings, "max_chunks_per_page", 2) or 2)
        per_source_chars = int(eff.get("max_chars_per_source") or getattr(settings, "max_chars_per_source", 800) or 800)

        evaluated: list = []
        for cand in candidates:
            cand = evaluate_authority_fitness(
                cand,
                intent=intent,
                knowledge_plan=knowledge_plan,
                understanding=understanding,
                profile=profile,
            )
            meta = source_meta.get(cand.source_id, {})
            cand = apply_section_selection(
                cand,
                intent=intent,
                knowledge_plan=knowledge_plan,
                main_content=meta.get("main_content", ""),
                max_chars=per_source_chars,
            )
            evaluated.append(cand)

        selected, rejected = select_by_coverage(
            evaluated,
            knowledge_plan=knowledge_plan,
            max_items=max(max_sources * max_chunks, max_sources),
            max_per_source=max_chunks,
        )

        contradictions = detect_contradictions(selected)
        has_instruction = bool(planner_decision.answer_plan.scope_instruction.strip())
        packed, packing_decisions, budget_truncated = pack_selected_evidence(
            selected,
            settings=settings,
            system_prompt=system_prompt,
            user_message=user_message or query,
            has_instruction=has_instruction,
        )

        if lang_excluded:
            for ex in lang_excluded:
                packing_decisions.append(ex)

        sufficiency = assess_plan_sufficiency(
            packed,
            knowledge_plan=knowledge_plan,
            contradiction_count=len(contradictions),
            budget_truncated=budget_truncated,
        )

        ordered_hits: list[SearchHit] = []
        for item in packed:
            hit = item.candidate.raw_hit
            if hit is not None:
                ordered_hits.append(hit)

        return EvidencePlan(
            intent=intent,
            knowledge_plan=knowledge_plan,
            selected=packed,
            rejected=rejected,
            sufficiency=sufficiency,
            contradictions=contradictions,
            packing_decisions=packing_decisions,
            candidate_count=len(candidates),
            plan_ms=int((perf_counter() - t0) * 1000),
            ordered_hits=ordered_hits,
        )

    def _load_sources(self, source_ids: set[int]) -> dict[int, dict]:
        if not self.db or not source_ids:
            return {}
        rows = self.db.execute(select(Source).where(Source.id.in_(source_ids))).scalars().all()
        return {
            s.id: {
                "main_content": (s.main_content_text or "").strip(),
                "summary": (s.llm_summary or "").strip(),
            }
            for s in rows
        }
