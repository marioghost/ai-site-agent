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
    # Exact content_hash groups: keep a single primary source.
    max_per_group = 1 if candidate.duplicate_group.startswith("hash:") else 2
    if used_groups.get(candidate.duplicate_group, 0) >= max_per_group:
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

    from app.services.language_resolver_service import normalize_url_for_lang_dedupe

    by_group: dict[str, list[EvidenceCandidate]] = {}
    for c in candidates:
        # Collapse bilingual URL twins here; hash-based republish control is in diversity_allows.
        lang_base = normalize_url_for_lang_dedupe(c.url)
        key = f"lang:{lang_base}" if lang_base else c.duplicate_group
        by_group.setdefault(key, []).append(c)

    kept: list[EvidenceCandidate] = []
    excluded: list[dict] = []
    seen_ids: set[str] = set()

    for group, items in by_group.items():
        if len(items) == 1:
            kept.append(items[0])
            seen_ids.add(items[0].candidate_id)
            continue
        preferred = [i for i in items if i.language == query_language]
        # Prefer query language, then authority fitness, then retrieval score.
        pool = preferred or items
        chosen = max(
            pool,
            key=lambda c: (c.authority_fitness, c.rerank_score, c.quality_score),
        )
        kept.append(chosen)
        seen_ids.add(chosen.candidate_id)
        for other in items:
            if other.candidate_id == chosen.candidate_id:
                continue
            seen_ids.add(other.candidate_id)
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
