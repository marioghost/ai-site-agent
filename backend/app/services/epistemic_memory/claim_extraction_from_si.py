"""Map Source Intelligence output to in-memory claim proposals (RFC-100 Step 029).

Read-only transformation — no DB writes, no memory_version changes, no integration
with chat/retrieval/indexing. Shadow persistence arrives in Step 030+.
"""
from __future__ import annotations

import json
import re

from app.models.source import Source
from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.epistemic_memory.proposal_types import ClaimProposal, EvidenceProposal
from app.services.source_intelligence_constants import SOURCE_INTELLIGENCE_VERSION
from app.services.source_intelligence_service import SourceIntelligenceService, SourceProfile

MIN_PROFILE_CONFIDENCE = 0.35
MIN_MAIN_TOPIC_CONFIDENCE = 0.45
MIN_PURPOSE_CONFIDENCE = 0.5
MIN_SUMMARY_CHARS = 15
MAX_PROPOSITION_CHARS = 2000

# Generic attribution — no site-type or industry hardcoding.
ATTRIBUTED_TO = "source_intelligence"
PROVENANCE_KIND = "source_intelligence"
PROPOSAL_STATUS = "proposal"


class ClaimExtractionFromSI:
    """Convert SI profiles into conservative claim proposals."""

    def extract_from_source(self, source: Source) -> list[ClaimProposal]:
        profile = SourceIntelligenceService.profile_from_source(source)
        if profile is None:
            return []
        return self.extract_from_profile(source, profile)

    def extract_from_profile(
        self, source: Source, profile: SourceProfile
    ) -> list[ClaimProposal]:
        if not _profile_is_usable(profile):
            return []

        semantic = SourceSemanticProfile.from_storage(profile.semantic)
        proposals: list[ClaimProposal] = []
        seen: set[str] = set()

        summary_claim = _proposal_from_summary(source, profile)
        if summary_claim and _remember(seen, summary_claim.proposition):
            proposals.append(summary_claim)

        topic_claim = _proposal_from_main_topic(source, profile, semantic)
        if topic_claim and _remember(seen, topic_claim.proposition):
            proposals.append(topic_claim)

        purpose_claim = _proposal_from_document_purpose(source, profile, semantic)
        if purpose_claim and _remember(seen, purpose_claim.proposition):
            proposals.append(purpose_claim)

        if not proposals:
            fallback = _proposal_from_subtopics(source, profile, semantic)
            if fallback and _remember(seen, fallback.proposition):
                proposals.append(fallback)

        return proposals


def _profile_is_usable(profile: SourceProfile) -> bool:
    if profile.confidence is None or profile.confidence < MIN_PROFILE_CONFIDENCE:
        return False
    if not (profile.llm_summary or profile.semantic):
        return False
    return True


def _remember(seen: set[str], proposition: str) -> bool:
    key = _normalize_proposition(proposition)
    if not key or key in seen:
        return False
    seen.add(key)
    return True


def _normalize_proposition(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _clamp_proposition(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) < MIN_SUMMARY_CHARS:
        return ""
    return cleaned[:MAX_PROPOSITION_CHARS]


def _scope_json(
    *,
    source: Source,
    profile: SourceProfile,
    proposal_kind: str,
    extra: dict | None = None,
) -> str:
    payload = {
        "source_id": source.id,
        "url": source.url,
        "document_type": profile.document_type,
        "page_role": profile.page_role,
        "proposal_kind": proposal_kind,
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _provenance_ref(source: Source, profile: SourceProfile) -> str:
    version = profile.profile_version or SOURCE_INTELLIGENCE_VERSION
    return f"source:{source.id}:si:{version}"


def _evidence_for_source(source: Source, profile: SourceProfile, excerpt: str) -> EvidenceProposal:
    clipped = (excerpt or "")[:2000] or None
    content_hash = getattr(source, "content_hash", None)
    return EvidenceProposal(
        excerpt=clipped,
        content_hash=content_hash,
        source_id=source.id,
        chunk_id=None,
        observation_key_hint=f"obs:source:{source.id}:si",
        role="support",
    )


def _base_proposal(
    *,
    source: Source,
    profile: SourceProfile,
    proposition: str,
    proposal_kind: str,
    confidence: float | None,
    scope_extra: dict | None = None,
    evidence_excerpt: str,
) -> ClaimProposal | None:
    text = _clamp_proposition(proposition)
    if not text:
        return None
    conf = confidence if confidence is not None else profile.confidence
    return ClaimProposal(
        proposition=text,
        scope_json=_scope_json(
            source=source,
            profile=profile,
            proposal_kind=proposal_kind,
            extra=scope_extra,
        ),
        epistemic_status=PROPOSAL_STATUS,
        attributed_to=ATTRIBUTED_TO,
        provenance_kind=PROVENANCE_KIND,
        provenance_ref=_provenance_ref(source, profile),
        confidence=round(conf, 3) if conf is not None else None,
        source_id=source.id,
        source_url=source.url,
        proposal_kind=proposal_kind,
        evidence=(_evidence_for_source(source, profile, evidence_excerpt),),
    )


def _proposal_from_summary(source: Source, profile: SourceProfile) -> ClaimProposal | None:
    summary = (profile.llm_summary or "").strip()
    if len(summary) < MIN_SUMMARY_CHARS:
        return None
    return _base_proposal(
        source=source,
        profile=profile,
        proposition=summary,
        proposal_kind="llm_summary",
        confidence=profile.confidence,
        evidence_excerpt=summary,
    )


def _proposal_from_main_topic(
    source: Source,
    profile: SourceProfile,
    semantic: SourceSemanticProfile | None,
) -> ClaimProposal | None:
    if semantic is None or not semantic.main_topic:
        return None
    topic_conf = semantic.main_topic_confidence or semantic.confidence or 0.0
    if topic_conf < MIN_MAIN_TOPIC_CONFIDENCE:
        return None
    topic = semantic.main_topic.strip()
    if len(topic) < 3:
        return None
    return _base_proposal(
        source=source,
        profile=profile,
        proposition=topic,
        proposal_kind="main_topic",
        confidence=topic_conf,
        scope_extra={"main_topic": topic},
        evidence_excerpt=profile.llm_summary or topic,
    )


def _proposal_from_document_purpose(
    source: Source,
    profile: SourceProfile,
    semantic: SourceSemanticProfile | None,
) -> ClaimProposal | None:
    if semantic is None or not semantic.document_purpose:
        return None
    purpose_conf = semantic.document_purpose_confidence or 0.0
    if purpose_conf < MIN_PURPOSE_CONFIDENCE:
        return None
    purpose = semantic.document_purpose.strip()
    if len(purpose) < 3:
        return None
    topic = (semantic.main_topic or "").strip()
    if topic:
        proposition = f"{topic}: {purpose.replace('_', ' ')}."
    else:
        proposition = purpose.replace("_", " ").capitalize() + "."
    return _base_proposal(
        source=source,
        profile=profile,
        proposition=proposition,
        proposal_kind="document_purpose",
        confidence=min(purpose_conf, profile.confidence or purpose_conf),
        scope_extra={
            "document_purpose": purpose,
            "main_topic": topic or None,
        },
        evidence_excerpt=profile.llm_summary or proposition,
    )


def _proposal_from_subtopics(
    source: Source,
    profile: SourceProfile,
    semantic: SourceSemanticProfile | None,
) -> ClaimProposal | None:
    """Fallback when no summary/topic/purpose — use subtopics only if clearly present."""
    if semantic is None or semantic.main_topic:
        return None
    subtopics = [s.strip() for s in semantic.subtopics if s and s.strip()]
    if not subtopics or (semantic.confidence or 0.0) < MIN_MAIN_TOPIC_CONFIDENCE:
        return None
    joined = "; ".join(subtopics[:3])
    proposition = f"Topics covered: {joined}."
    return _base_proposal(
        source=source,
        profile=profile,
        proposition=proposition,
        proposal_kind="subtopics",
        confidence=semantic.confidence,
        scope_extra={"subtopics": subtopics[:3]},
        evidence_excerpt=profile.llm_summary or joined,
    )
