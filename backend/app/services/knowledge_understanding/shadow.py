"""Phase 1 Understanding shadow — observe vs DFP; never mutate ranking."""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.settings import Settings
from app.services.feature_flags import knowledge_understanding_enabled
from app.services.knowledge_understanding.factory import get_understanding_layer
from app.services.rag_planning.contracts import PlannerDecision
from app.services.retrieval_engine.pipeline import DocumentRetrievalResult
from app.services.retrieval_engine.query_understanding import QueryUnderstanding

logger = get_logger(__name__)

SHADOW_BUDGET_MS = 250


@dataclass(frozen=True)
class _NeedAdapter:
    """Structural QueryNeedInput from planner understanding."""

    query: str
    topic: str | None
    expected_answer_type: str
    semantic_focus: str
    intent: str
    focus_terms: list[str]


def run_understanding_shadow(
    db: Session,
    settings: Settings,
    *,
    doc_result: DocumentRetrievalResult,
    planner_decision: PlannerDecision | None,
    query: str,
    query_vector: list[float] | None = None,
) -> dict[str, Any]:
    """Compare Understanding evidence to DFP candidates. Soft-fail; no ranking effect."""
    t0 = perf_counter()
    base: dict[str, Any] = {
        "understanding_shadow_enabled": False,
        "snapshot_id": None,
        "knowledge_version": None,
        "resolved_concepts": [],
        "concept_confidence": [],
        "understanding_evidence_source_ids": [],
        "dfp_source_ids": [],
        "overlap_source_ids": [],
        "overlap_count": 0,
        "dfp_count": 0,
        "understanding_count": 0,
        "overlap_ratio": 0.0,
        "understanding_only_count": 0,
        "dfp_only_count": 0,
        "resolution_latency_ms": 0,
        "evidence_lookup_latency_ms": 0,
        "total_understanding_shadow_ms": 0,
        "failure_reason": None,
        "why_summary": "",
    }

    dfp_ids = _dfp_source_ids(doc_result)
    base["dfp_source_ids"] = dfp_ids
    base["dfp_count"] = len(dfp_ids)

    if not knowledge_understanding_enabled(settings):
        base["failure_reason"] = "flag_off"
        base["total_understanding_shadow_ms"] = _ms(t0)
        return base

    base["understanding_shadow_enabled"] = True

    try:
        layer = get_understanding_layer(db, settings)
        summary = layer.summary()
        base["snapshot_id"] = summary.snapshot_id
        base["knowledge_version"] = summary.knowledge_version
        if summary.status != "ready" or not summary.snapshot_id:
            base["failure_reason"] = summary.error_message or f"snapshot_{summary.status or 'missing'}"
            base["why_summary"] = "No ready Understanding snapshot for shadow compare."
            base["total_understanding_shadow_ms"] = _ms(t0)
            return base

        need_input = _need_from_planner(planner_decision, query)
        t_resolve = perf_counter()
        need = layer.resolve_query(need_input, query_embedding=query_vector)
        base["resolution_latency_ms"] = _ms(t_resolve)
        base["resolved_concepts"] = [
            {"key": c.concept_key, "label": c.label, "confidence": round(c.confidence, 4)}
            for c in need.concepts[:12]
        ]
        base["concept_confidence"] = [round(c.confidence, 4) for c in need.concepts[:12]]

        t_find = perf_counter()
        matches = layer.find_evidence(need, limit=24)
        base["evidence_lookup_latency_ms"] = _ms(t_find)

        u_ids = sorted({int(m.source_id) for m in matches if m.source_id})
        base["understanding_evidence_source_ids"] = u_ids
        base["understanding_count"] = len(u_ids)

        dfp_set = set(dfp_ids)
        u_set = set(u_ids)
        overlap = sorted(dfp_set & u_set)
        base["overlap_source_ids"] = overlap
        base["overlap_count"] = len(overlap)
        base["understanding_only_count"] = len(u_set - dfp_set)
        base["dfp_only_count"] = len(dfp_set - u_set)
        base["overlap_ratio"] = (
            round(len(overlap) / len(dfp_set), 4) if dfp_set else 0.0
        )
        labels = ", ".join(c.label for c in need.concepts[:5]) or "unresolved"
        base["why_summary"] = (
            f"Shadow resolved [{labels}] → {len(u_ids)} understanding sources; "
            f"{len(overlap)} overlap with {len(dfp_ids)} DFP candidates "
            f"(ratio={base['overlap_ratio']})."
        )
        if matches:
            base["match_explanations"] = [
                {"source_id": m.source_id, "why": m.why, "score": round(m.understanding_score, 4)}
                for m in matches[:8]
            ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("understanding_shadow_failed error=%s", type(exc).__name__)
        base["failure_reason"] = f"{type(exc).__name__}: {exc}"[:500]
        base["why_summary"] = "Understanding shadow soft-failed; production retrieval unchanged."

    base["total_understanding_shadow_ms"] = _ms(t0)
    if base["total_understanding_shadow_ms"] > SHADOW_BUDGET_MS:
        logger.info(
            "understanding_shadow_slow duration_ms=%s budget_ms=%s",
            base["total_understanding_shadow_ms"],
            SHADOW_BUDGET_MS,
        )
    return base


def _dfp_source_ids(doc_result: DocumentRetrievalResult) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for doc in doc_result.selected_documents or []:
        sid = getattr(doc, "source_id", None)
        if sid is None and getattr(doc, "representative_chunk", None) is not None:
            sid = getattr(doc.representative_chunk, "source_id", None)
        if sid is None:
            continue
        sid_i = int(sid)
        if sid_i not in seen:
            seen.add(sid_i)
            ids.append(sid_i)
    if ids:
        return ids
    for hit in doc_result.selected_hits or []:
        sid = getattr(hit, "source_id", None)
        if sid is None:
            continue
        sid_i = int(sid)
        if sid_i not in seen:
            seen.add(sid_i)
            ids.append(sid_i)
    return ids


def _need_from_planner(
    planner_decision: PlannerDecision | None,
    query: str,
) -> _NeedAdapter:
    understanding: QueryUnderstanding | None = None
    if planner_decision is not None:
        understanding = getattr(planner_decision, "understanding", None)
    if understanding is not None:
        return _NeedAdapter(
            query=getattr(understanding, "query", None) or query,
            topic=getattr(understanding, "topic", None),
            expected_answer_type=str(
                getattr(understanding, "expected_answer_type", None) or "general"
            ),
            semantic_focus=str(getattr(understanding, "semantic_focus", None) or "general"),
            intent=str(getattr(understanding, "intent", None) or "general"),
            focus_terms=list(getattr(understanding, "focus_terms", None) or []),
        )
    kp = getattr(planner_decision, "knowledge_plan", None) if planner_decision else None
    return _NeedAdapter(
        query=query,
        topic=None,
        expected_answer_type=str(getattr(kp, "answer_type", None) or "general"),
        semantic_focus=str(getattr(kp, "semantic_focus", None) or "general"),
        intent=str(getattr(kp, "information_need", None) or "general"),
        focus_terms=[],
    )


def _ms(t0: float) -> int:
    return int((perf_counter() - t0) * 1000)
