"""Evidence planner — single decision owner for final context selection."""
from __future__ import annotations

import json
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
from app.services.evidence_planning.types import EvidencePlan, RejectedEvidence
from app.services.context_builder_service import ContextBuilderService
from app.services.llm_mode_service import effective_generation_settings
from app.services.qdrant_service import SearchHit
from app.services.rag_planning.contracts import PlannerDecision
from app.services.retrieval_engine.focus_compatibility import is_strong_compatibility


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

        # Prefer query-language URL variants before evidence normalization.
        hits, bilingual_excluded = ContextBuilderService.dedupe_bilingual_hits_with_report(
            hits, query_language
        )

        candidates = normalize_hits(
            hits,
            intent=intent,
            profile=profile,
            query_language=query_language,
            document_scores=document_scores,
        )

        source_meta = self._load_sources({c.source_id for c in candidates})
        # Stamp SI fields onto candidates for hash diversity + purpose authority.
        for cand in candidates:
            meta = source_meta.get(cand.source_id, {})
            ch = (meta.get("content_hash") or "").strip()
            if ch:
                if cand.raw_hit is not None and not getattr(cand.raw_hit, "content_hash", ""):
                    cand.raw_hit.content_hash = ch
                if not cand.duplicate_group.startswith("hash:"):
                    from app.services.evidence_planning.normalizer import _duplicate_group

                    cand.duplicate_group = _duplicate_group(cand.url, cand.text, ch)
            purpose = (meta.get("document_purpose") or "").strip()
            if purpose and (
                not cand.source_purpose
                or cand.source_purpose in {"generic", "general information"}
            ):
                cand.source_purpose = purpose
            cq = int(meta.get("content_quality") or 0)
            if cq > 0:
                bp_q = max(0.0, min(1.0, 1.0 - float(
                    getattr(cand.raw_hit, "boilerplate_ratio", 0.0) if cand.raw_hit else 0.0
                )))
                cand.quality_score = max(
                    0.0, min(1.0, 0.55 * cand.quality_score + 0.45 * (cq / 100.0) * (0.5 + 0.5 * bp_q))
                )

        # Authority first so language dedupe can prefer the fitter language twin.
        for i, cand in enumerate(candidates):
            candidates[i] = evaluate_authority_fitness(
                cand,
                intent=intent,
                knowledge_plan=knowledge_plan,
                understanding=understanding,
                profile=profile,
            )

        candidates, lang_excluded = dedupe_language_candidates(candidates, query_language)
        if bilingual_excluded:
            lang_excluded = list(bilingual_excluded) + list(lang_excluded)

        eff = effective_generation_settings(settings)
        max_sources = int(eff.get("max_sources_in_prompt") or getattr(settings, "max_sources_in_prompt", 3) or 3)
        max_chunks = int(getattr(settings, "max_chunks_per_page", 2) or 2)
        per_source_chars = int(eff.get("max_chars_per_source") or getattr(settings, "max_chars_per_source", 800) or 800)

        evaluated: list = []
        for cand in candidates:
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

        # Do not ship contaminated packages for strict foci when goal is unmet.
        focus = getattr(knowledge_plan, "semantic_focus", "") or ""
        if (
            focus
            in {
                "definition",
                "product_specification",
                "rates",
                "locator",
                "organization_profile",
            }
            and sufficiency.level in {"weak", "no_evidence"}
            and not sufficiency.expected_evidence_matched
            and packed
        ):
            strong = [
                item
                for item in packed
                if is_strong_compatibility(item.candidate.compatibility_label)
            ]
            demoted = [item for item in packed if item not in strong]
            # Prefer honest weak package over total empty when only adjacent evidence exists.
            if strong:
                for item in demoted:
                    rejected.append(
                        RejectedEvidence(
                            candidate=item.candidate,
                            rejection_reason="expected_evidence_mismatch",
                        )
                    )
                packed = strong
            elif demoted:
                packed = demoted[:1]
                for item in demoted[1:]:
                    rejected.append(
                        RejectedEvidence(
                            candidate=item.candidate,
                            rejection_reason="expected_evidence_mismatch",
                        )
                    )
            else:
                packed = []
            sufficiency = assess_plan_sufficiency(
                packed,
                knowledge_plan=knowledge_plan,
                contradiction_count=len(contradictions),
                budget_truncated=budget_truncated,
            )
            packing_decisions.append(
                {
                    "action": "goal_satisfaction_filter",
                    "removed": len(demoted) if strong else max(0, len(demoted) - len(packed)),
                    "kept": len(packed),
                    "focus": focus,
                }
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
        out: dict[int, dict] = {}
        for s in rows:
            purpose = ""
            try:
                sem = json.loads(getattr(s, "intelligence_json", None) or "{}")
                if isinstance(sem, dict):
                    purpose = str(sem.get("document_purpose") or "").strip()
            except (TypeError, ValueError, json.JSONDecodeError):
                purpose = ""
            out[s.id] = {
                "main_content": (s.main_content_text or "").strip(),
                "summary": (s.llm_summary or "").strip(),
                "content_hash": (s.content_hash or "").strip(),
                "document_purpose": purpose,
                "content_quality": int(getattr(s, "content_quality", 0) or 0),
            }
        return out
