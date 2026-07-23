"""Stage 12 — automatic profile repair."""
from __future__ import annotations

import re
from copy import deepcopy

from app.schemas.knowledge_profile import (
    ContentHintRule,
    DocumentTypeRule,
    ImportantTopic,
    KnowledgeProfile,
)
from app.services.knowledge_profile_generation.alias_utils import dedupe_topic_aliases
from app.services.knowledge_profile_generation.content_hint_discovery import (
    ContentHintDiscovery,
    _slug_hint,
)
from app.services.knowledge_profile_generation.models import (
    ContentHintCandidate,
    DetectedOrganization,
    DiscoveredTopic,
    ValidationIssue,
)
from app.services.knowledge_profile_service import generic_corporate_profile


class ProfileAutoRepair:
    def repair(
        self,
        profile: KnowledgeProfile,
        issues: list[ValidationIssue],
        *,
        organization: DetectedOrganization | None = None,
        topics: list[DiscoveredTopic] | None = None,
        hint_candidates: list[ContentHintCandidate] | None = None,
    ) -> tuple[KnowledgeProfile, list[ValidationIssue], int]:
        fixed = deepcopy(profile)
        repairs = 0
        updated_issues: list[ValidationIssue] = []

        hint_registry = {_slug_hint(h.hint_id): h for h in (hint_candidates or [])}
        hint_ids = set(hint_registry.keys()) | {r.content_type_hint for r in fixed.content_hint_rules}

        for issue in issues:
            repaired = False
            if issue.code == "missing_organization" and organization:
                fixed.organization_name = organization.name
                fixed.site_display_name = organization.name
                fixed.organization_aliases = list(organization.aliases)
                repaired = True

            elif issue.code == "unknown_content_hint":
                m = re.search(r"hint '([^']+)'", issue.message)
                if m:
                    hint = m.group(1)
                    hid = _slug_hint(hint)
                    if hid not in hint_ids:
                        cand = ContentHintCandidate(
                            hint_id=hid,
                            patterns=[hint.replace("_", " ")],
                            confidence=0.4,
                        )
                        hint_registry[hid] = cand
                        fixed.content_hint_rules.append(
                            ContentHintRule(
                                content_type_hint=hid,
                                patterns=cand.patterns,
                                priority=35,
                            )
                        )
                        hint_ids.add(hid)
                    repaired = True

            elif issue.code == "duplicate_topic_keys" and topics:
                seen: set[str] = set()
                deduped: list[ImportantTopic] = []
                for t in fixed.important_topics:
                    if t.key in seen:
                        repairs += 1
                        continue
                    seen.add(t.key)
                    deduped.append(t)
                fixed.important_topics = deduped
                repaired = True

            elif issue.code == "duplicate_alias":
                repaired = self._merge_duplicate_alias(fixed, issue)
                if repaired:
                    repairs += 1

            elif issue.code == "unknown_document_type":
                m = re.search(r"type '([^']+)'", issue.message)
                if m:
                    dt = m.group(1)
                    if not any(r.document_type == dt for r in fixed.document_type_rules):
                        fixed.document_type_rules.append(
                            DocumentTypeRule(document_type=dt, url_patterns=[], priority=40)
                        )
                    repaired = True

            if repaired:
                repairs += 1
                updated_issues.append(issue.model_copy(update={"auto_repaired": True}))
            else:
                updated_issues.append(issue)

        if not fixed.document_type_rules:
            seed = generic_corporate_profile()
            fixed.document_type_rules = seed.document_type_rules
            repairs += 1

        if not fixed.content_hint_rules and hint_registry:
            discovery = ContentHintDiscovery()
            for cand in hint_registry.values():
                discovery.register(cand)
            fixed.content_hint_rules = discovery.to_rules()
            repairs += 1

        if topics and len(fixed.important_topics) < 2:
            fixed.important_topics = self._topics_from_discovered(topics, hint_ids)
            repairs += 1

        fixed, alias_fixes = dedupe_topic_aliases(fixed)
        if alias_fixes:
            repairs += alias_fixes
            updated_issues = [
                issue.model_copy(update={"auto_repaired": True})
                if issue.code == "duplicate_alias"
                else issue
                for issue in updated_issues
            ]

        return fixed, updated_issues, repairs

    def _merge_duplicate_alias(self, profile: KnowledgeProfile, issue: ValidationIssue) -> bool:
        _, removed = dedupe_topic_aliases(profile)
        return removed > 0

    def _topics_from_discovered(
        self, topics: list[DiscoveredTopic], hint_ids: set[str]
    ) -> list[ImportantTopic]:
        out: list[ImportantTopic] = []
        for t in topics[:12]:
            hints = [h for h in t.preferred_content_hints if _slug_hint(h) in hint_ids]
            out.append(
                ImportantTopic(
                    key=t.id,
                    label=t.title,
                    aliases=t.aliases,
                    preferred_document_types=t.preferred_document_types,
                    preferred_content_hints=hints,
                    answer_strategy=t.answer_strategy,  # type: ignore[arg-type]
                )
            )
        return out
