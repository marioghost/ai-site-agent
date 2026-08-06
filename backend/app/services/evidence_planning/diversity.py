"""Diversity and redundancy constraints."""
from __future__ import annotations

from app.services.evidence_planning.types import EvidenceCandidate, SelectedEvidence
from app.services.rag_planning.contracts import KnowledgePlan


def diversity_allows(
    candidate: EvidenceCandidate,
    selected: list[SelectedEvidence],
    used_groups: dict[str, int],
    knowledge_plan: KnowledgePlan,
) -> bool:
    if used_groups.get(candidate.duplicate_group, 0) >= 2:
        return False
    same_source = sum(1 for s in selected if s.candidate.source_id == candidate.source_id)
    if same_source >= 2:
        return False
    if not selected:
        return True
    if candidate.broad_injected:
        has_stronger = any(
            s.candidate.authority_fitness >= candidate.authority_fitness + 0.05
            and not s.candidate.broad_injected
            and s.candidate.kp_preferred
            for s in selected
        )
        if has_stronger:
            overlap = candidate.available_aspects & set(knowledge_plan.required_slots)
            if not overlap or candidate.authority_fitness < 0.55:
                return False
    return True


def dedupe_language_candidates(
    candidates: list[EvidenceCandidate],
    query_language: str,
) -> tuple[list[EvidenceCandidate], list[dict]]:
    if query_language in {"", "unknown"} or len(candidates) < 2:
        return candidates, []

    by_group: dict[str, list[EvidenceCandidate]] = {}
    for c in candidates:
        by_group.setdefault(c.duplicate_group, []).append(c)

    kept: list[EvidenceCandidate] = []
    excluded: list[dict] = []
    seen_ids: set[str] = set()

    for group, items in by_group.items():
        if len(items) == 1:
            kept.append(items[0])
            seen_ids.add(items[0].candidate_id)
            continue
        preferred = [i for i in items if i.language == query_language]
        chosen = max(preferred or items, key=lambda c: c.authority_fitness)
        kept.append(chosen)
        seen_ids.add(chosen.candidate_id)
        for other in items:
            if other.candidate_id == chosen.candidate_id:
                continue
            excluded.append(
                {
                    "url": other.url,
                    "language": other.language,
                    "duplicate_group": group,
                    "reason": "language_duplicate",
                }
            )

    for c in candidates:
        if c.candidate_id not in seen_ids:
            kept.append(c)
            seen_ids.add(c.candidate_id)
    return kept, excluded
