"""Evidence Finder — resolved knowledge need → source candidates."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from app.services.knowledge_understanding.diagnostics import explain_evidence_match
from app.services.knowledge_understanding.models import (
    Concept,
    EvidenceLink,
    ResolvedNeed,
    UnderstandingMatch,
)


class EvidenceFinder:
    """Lookup evidence from the concept index for a resolved need."""

    def find(
        self,
        need: ResolvedNeed,
        *,
        evidence: Sequence[EvidenceLink],
        concepts: Sequence[Concept],
        source_meta: Mapping[int, tuple[str, str]] | None = None,
        limit: int = 24,
    ) -> list[UnderstandingMatch]:
        if not need.concepts or not evidence:
            return []

        concept_by_key = {c.concept_key: c for c in concepts}
        keys = {c.concept_key for c in need.concepts}
        # Aggregate score per source.
        scores: dict[int, float] = defaultdict(float)
        matched_keys: dict[int, set[str]] = defaultdict(set)
        canonical_bonus: dict[int, float] = defaultdict(float)

        for link in evidence:
            if link.concept_key not in keys:
                continue
            if link.relation not in {"explains", "mentions", "supports", "answers"}:
                continue
            weight = float(link.weight)
            if link.relation == "explains":
                weight *= 1.0
            elif link.relation == "mentions":
                weight *= 0.7
            elif link.relation == "supports":
                weight *= 0.45
            else:
                weight *= 0.6
            scores[link.source_id] += weight * max(link.confidence, 0.2)
            matched_keys[link.source_id].add(link.concept_key)

        for concept in need.concepts:
            if concept.canonical_source_id is not None:
                canonical_bonus[concept.canonical_source_id] += 0.25 * max(concept.confidence, 0.3)

        ranked: list[UnderstandingMatch] = []
        meta = source_meta or {}
        for source_id, base in scores.items():
            score = base + canonical_bonus.get(source_id, 0.0)
            keys_hit = tuple(sorted(matched_keys[source_id]))
            labels = tuple(
                concept_by_key[k].label for k in keys_hit if k in concept_by_key
            )
            url, title = meta.get(source_id, ("", ""))
            is_canonical = any(
                concept_by_key[k].canonical_source_id == source_id
                for k in keys_hit
                if k in concept_by_key
            )
            why = explain_evidence_match(
                labels=labels,
                is_canonical=is_canonical,
                need_type=need.need_type,
            )
            ranked.append(
                UnderstandingMatch(
                    source_id=source_id,
                    understanding_score=round(min(1.0, score), 4),
                    why=why,
                    concept_keys=keys_hit,
                    url=url,
                    title=title,
                )
            )

        ranked.sort(key=lambda m: m.understanding_score, reverse=True)
        return ranked[: max(1, limit)]
