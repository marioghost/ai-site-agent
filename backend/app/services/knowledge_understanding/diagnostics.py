"""Human-language understanding diagnostics — why evidence matched, not structure dumps."""
from __future__ import annotations

from collections.abc import Sequence

from app.services.knowledge_understanding.models import (
    ResolvedNeed,
    UnderstandingMatch,
)


def explain_evidence_match(
    *,
    labels: Sequence[str],
    is_canonical: bool,
    need_type: str,
) -> str:
    """Explain why a source fits the understood need."""
    topics = [t for t in labels if t]
    if not topics:
        base = "This source relates to the knowledge needed for the query."
    elif len(topics) == 1:
        base = f"This source explains {topics[0]}."
    else:
        head = ", ".join(topics[:-1])
        base = f"This source explains {head} and {topics[-1]}."

    if is_canonical:
        if topics:
            base = (
                f"This source directly explains {topics[0]} and is the canonical page "
                f"for that topic."
            )
        else:
            base = "This source is the canonical page for the resolved topic."

    if need_type and need_type not in {"general", "unknown"}:
        base = f"{base.rstrip('.')} (matches a {need_type.replace('_', ' ')} need)."
    return base


def build_understanding_trace(
    *,
    enabled: bool,
    need: ResolvedNeed | None,
    matches: Sequence[UnderstandingMatch],
    selected_limit: int = 3,
) -> dict:
    """Diagnostics payload describing understanding decisions in human language."""
    if not enabled:
        return {"enabled": False}

    concepts = list(need.concepts) if need else []
    top = list(matches)[:selected_limit]
    return {
        "enabled": True,
        "resolved_concepts": [c.label for c in concepts],
        "resolved_need": need.need_type if need else "general",
        "resolution_method": need.resolution_method if need else "none",
        "evidence_matches": [
            {
                "source_id": m.source_id,
                "url": m.url,
                "title": m.title,
                "why": m.why,
                "understanding_score": m.understanding_score,
            }
            for m in top
        ],
        "understanding_candidates": len(matches),
        "understanding_selected": len(top),
    }


def explain_match_for_source(
    source_id: int,
    need: ResolvedNeed,
    matches: Sequence[UnderstandingMatch],
) -> str:
    for match in matches:
        if match.source_id == source_id:
            return match.why
    if need.concepts:
        labels = ", ".join(c.label for c in need.concepts[:3])
        return f"No understanding match for this source against {labels}."
    return "No resolved knowledge need for this query."
