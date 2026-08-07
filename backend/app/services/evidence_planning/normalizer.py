"""Normalize retrieval hits into evidence candidates."""
from __future__ import annotations

import hashlib
import re

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.rag_planning.purpose_catalog import (
    infer_knowledge_slots,
    normalize_content_hint_to_purpose,
    purpose_from_metadata,
)
from app.services.evidence_planning.types import EvidenceCandidate
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.llm_options_service import estimate_tokens
from app.services.qdrant_service import SearchHit
from app.services.source_intelligence_constants import DOCUMENT_TYPE_TO_ROLE

_INJECT_PREFIX = "broad_inject"


def is_broad_injected(hit: SearchHit) -> bool:
    return (hit.selection_reason or "").lower().startswith(_INJECT_PREFIX)


def effective_page_role(hit: SearchHit) -> str:
    role = (hit.page_role or "").lower().strip()
    if role and role != "generic":
        return role
    doc = (hit.document_type or "generic_page").lower()
    return DOCUMENT_TYPE_TO_ROLE.get(doc, "generic")


def _profile_flags(
    profile: KnowledgeProfile | None, intent: str, document_type: str
) -> tuple[bool, bool]:
    if profile is None:
        return False, False
    rule = KnowledgeProfileService.priority_rule_for_intent(profile, intent)
    if rule is None:
        return False, False
    doc = document_type.lower()
    preferred = doc in frozenset(rule.boost_document_types)
    deprioritized = doc in frozenset(rule.deprioritize_document_types)
    return preferred, deprioritized


def _duplicate_group(url: str, text: str, content_hash: str = "") -> str:
    """Prefer source content_hash so republished URLs collapse to one evidence group."""
    digest = (content_hash or "").strip().lower()
    if digest:
        return f"hash:{digest[:32]}"
    norm = re.sub(r"\s+", " ", (text or "")[:500].lower()).strip()
    text_digest = hashlib.sha1(norm.encode("utf-8", errors="ignore")).hexdigest()[:12]
    host = (url or "").split("/")[2] if "://" in (url or "") else url
    return f"{host}:{text_digest}"


def normalize_hits(
    hits: list[SearchHit],
    *,
    intent: str,
    profile: KnowledgeProfile | None = None,
    query_language: str = "unknown",
    document_scores: dict[int, float] | None = None,
) -> list[EvidenceCandidate]:
    """Merge and normalize hits; prefer naturally retrieved over injected duplicates."""
    merged: dict[str, SearchHit] = {}
    for hit in hits:
        key = f"{hit.source_id}:{hit.chunk_index}"
        prev = merged.get(key)
        if prev is None:
            merged[key] = hit
            continue
        if is_broad_injected(prev) and not is_broad_injected(hit):
            merged[key] = hit
        elif is_broad_injected(hit) and not is_broad_injected(prev):
            continue
        elif (hit.final_score or hit.score) > (prev.final_score or prev.score):
            merged[key] = hit

    candidates: list[EvidenceCandidate] = []
    for hit in merged.values():
        doc = hit.document_type or "generic_page"
        role = effective_page_role(hit)
        kp_pref, kp_depr = _profile_flags(profile, intent, doc)
        text = (hit.text or "").strip()
        heading = (hit.heading or "").strip()
        # Prefer SI document_purpose; map chunk hints into purpose vocabulary.
        purpose = (getattr(hit, "document_purpose", "") or "").strip()
        if not purpose:
            purpose = normalize_content_hint_to_purpose(
                getattr(hit, "content_type_hint", "") or ""
            )
        if purpose in {"", "generic"}:
            purpose = purpose_from_metadata(page_role=role, document_type=doc)
        aspects = infer_knowledge_slots(
            page_role=role,
            document_type=doc,
            source_purpose=purpose,
            heading=heading,
            text=text,
        )
        rerank = float(hit.final_score or hit.score or 0.0)
        if document_scores and hit.source_id in document_scores:
            rerank = max(rerank, document_scores[hit.source_id])
        injected = is_broad_injected(hit)
        breakdown = getattr(hit, "score_breakdown", None) or {}
        seeded_label = str(breakdown.get("compatibility_label") or "ambiguous")
        seeded_focus = float(breakdown.get("focus_match_score") or 0.0)
        quality = max(0.0, min(1.0, 1.0 - float(hit.boilerplate_ratio or 0.0)))
        cq = float(getattr(hit, "content_quality", 0) or 0)
        if cq > 0:
            quality = max(0.0, min(1.0, 0.55 * quality + 0.45 * (cq / 100.0)))
        candidates.append(
            EvidenceCandidate(
                candidate_id=f"{hit.source_id}:{hit.chunk_index}",
                source_id=hit.source_id,
                chunk_index=hit.chunk_index,
                url=hit.url or "",
                title=hit.title or hit.url or "",
                heading=heading,
                text=text,
                document_type=doc,
                page_role=role,
                source_purpose=purpose,
                language=(hit.source_language or "unknown"),
                dense_score=float(hit.dense_score or 0.0),
                lexical_score=float(hit.lexical_score or 0.0),
                rerank_score=rerank,
                naturally_retrieved=not injected,
                broad_injected=injected,
                inject_reason=(hit.selection_reason or "") if injected else "",
                canonical=bool(hit.source_canonical or hit.is_canonical),
                kp_preferred=kp_pref,
                kp_deprioritized=kp_depr,
                quality_score=quality,
                answerability=0.5,
                intent_compatibility=0.5,
                focus_match_score=seeded_focus,
                compatibility_label=seeded_label,
                duplicate_group=_duplicate_group(
                    hit.url or "",
                    text,
                    getattr(hit, "content_hash", "") or "",
                ),
                available_aspects=aspects,
                section_text=text,
                section_heading=heading,
                token_estimate=max(1, estimate_tokens(len(text) + len(heading) + 40)),
                raw_hit=hit,
            )
        )
    return candidates
