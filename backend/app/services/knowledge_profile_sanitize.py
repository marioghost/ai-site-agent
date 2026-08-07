"""Make a Knowledge Profile persistable under validate_profile constraints."""
from __future__ import annotations

from copy import deepcopy

from app.schemas.knowledge_profile import (
    ContentHintRule,
    DocumentTypeRule,
    KnowledgeProfile,
)
from app.services.knowledge_profile_service import (
    KnowledgeProfileService,
    _generic_intent_rules,
    _topic_intent_rules,
)


def sanitize_profile_for_persist(profile: KnowledgeProfile) -> KnowledgeProfile:
    """Ensure referenced document types / hints exist and required fields are valid."""
    fixed = deepcopy(profile)
    fixed.important_topics = [t for t in fixed.important_topics if (t.key or "").strip()]

    doc_types = {r.document_type for r in fixed.document_type_rules}
    hint_types = {r.content_type_hint for r in fixed.content_hint_rules}

    needed_docs: set[str] = set()
    needed_hints: set[str] = set()
    for topic in fixed.important_topics:
        needed_docs.update(d for d in topic.preferred_document_types if d)
        needed_hints.update(h for h in topic.preferred_content_hints if h)
    for rule in fixed.source_priority_rules:
        needed_docs.update(rule.boost_document_types)
        needed_docs.update(rule.deprioritize_document_types)
        needed_hints.update(rule.boost_content_hints)
        needed_hints.update(rule.deprioritize_content_hints)

    for dt in sorted(needed_docs):
        if dt in doc_types or dt in {"homepage", "generic_page"}:
            continue
        fixed.document_type_rules.append(
            DocumentTypeRule(document_type=dt, url_patterns=[], priority=40)
        )
        doc_types.add(dt)

    for hint in sorted(needed_hints):
        if hint in hint_types or hint in {"generic", "overview"}:
            continue
        fixed.content_hint_rules.append(
            ContentHintRule(
                content_type_hint=hint,
                patterns=[hint.replace("_", " ")],
                priority=35,
            )
        )
        hint_types.add(hint)

    if not fixed.intents:
        fixed.intents = _generic_intent_rules() + _topic_intent_rules(fixed.important_topics)

    # Drop stale topic_key references after topic filtering.
    topic_keys = {t.key for t in fixed.important_topics}
    fixed.intents = [
        r
        for r in fixed.intents
        if not r.topic_key or r.topic_key in topic_keys
    ]

    return fixed


def prepare_profile_for_persist(profile: KnowledgeProfile) -> tuple[KnowledgeProfile, list[str]]:
    """Sanitize then validate; returns (profile, remaining errors)."""
    ready = sanitize_profile_for_persist(profile)
    return ready, KnowledgeProfileService.validate_profile(ready)
