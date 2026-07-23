"""Stage 8 — Knowledge Profile validation."""
from __future__ import annotations

from app.schemas.knowledge_profile import KnowledgeProfile
from app.services.knowledge_profile_generation.models import ValidationIssue
from app.services.knowledge_profile_service import KnowledgeProfileService


class KnowledgeProfileValidator:
    def validate(
        self,
        profile: KnowledgeProfile,
        *,
        registered_hint_ids: set[str] | None = None,
        allowed_topic_ids: set[str] | None = None,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if not profile.organization_name.strip():
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="missing_organization",
                    message="Organization name is required.",
                    field="organization_name",
                )
            )

        topic_keys = [t.key for t in profile.important_topics]
        if len(topic_keys) != len(set(topic_keys)):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="duplicate_topic_keys",
                    message="Important topic keys must be unique.",
                    field="important_topics",
                )
            )

        all_aliases: list[str] = []
        for topic in profile.important_topics:
            for alias in topic.aliases:
                al = alias.lower().strip()
                if al in all_aliases:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            code="duplicate_alias",
                            message=f"Duplicate alias '{alias}' across topics.",
                            field=f"topic:{topic.key}",
                        )
                    )
                all_aliases.append(al)

            if allowed_topic_ids and topic.key not in allowed_topic_ids:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="unknown_topic_id",
                        message=f"Topic '{topic.key}' was not discovered by pipeline.",
                        field=f"topic:{topic.key}",
                    )
                )

        doc_types = {r.document_type for r in profile.document_type_rules}
        hint_types = {r.content_type_hint for r in profile.content_hint_rules}
        if registered_hint_ids:
            hint_types = hint_types | registered_hint_ids

        for topic in profile.important_topics:
            for hint in topic.preferred_content_hints:
                if hint and hint not in hint_types and hint != "generic":
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="unknown_content_hint",
                            message=f"Topic '{topic.key}' references unknown content hint '{hint}'.",
                            field=f"topic:{topic.key}",
                        )
                    )
            for dt in topic.preferred_document_types:
                if dt and dt not in doc_types and dt not in {"homepage", "generic_page"}:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            code="unknown_document_type",
                            message=f"Topic '{topic.key}' references unknown document type '{dt}'.",
                            field=f"topic:{topic.key}",
                        )
                    )

        for rule in profile.source_priority_rules:
            for hint in rule.boost_content_hints + rule.deprioritize_content_hints:
                if hint and hint not in hint_types and hint not in {"generic", "overview"}:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="unknown_priority_hint",
                            message=f"Priority rule '{rule.query_intent}' references unknown hint '{hint}'.",
                            field="source_priority_rules",
                        )
                    )

        for err in KnowledgeProfileService.validate_profile(profile):
            code = "validation"
            if "unknown content hint" in err.lower():
                code = "unknown_content_hint"
            elif "unknown document type" in err.lower():
                code = "unknown_document_type"
            issues.append(
                ValidationIssue(
                    severity="error",
                    code=code,
                    message=err,
                )
            )

        return issues
