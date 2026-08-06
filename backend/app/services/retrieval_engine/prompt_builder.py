"""Compact prompt builder — admin system prompt is primary; intent cues stay thin."""
from __future__ import annotations

from app.services.context_builder_service import BuiltContext
from app.services.language_resolver_service import detect_query_language
from app.services.llm_mode_service import get_mode_profile
from app.services.qdrant_service import SearchHit
from app.services.source_intelligence_constants import PROMPT_TEMPLATE_VERSION
from app.services.system_prompt_defaults import DEFAULT_SYSTEM_PROMPT

# Re-export for callers that import from prompt_builder.
__all__ = ("CompactPromptBuilder", "DEFAULT_SYSTEM_PROMPT", "OVERVIEW_INTENTS")

OVERVIEW_INTENTS = frozenset({
    "entity_overview",
    "site_overview",
    "organization_overview",
    "topic_overview",
    "category_overview",
})

LISTING_INTENTS = frozenset({
    "product_query",
    "listing",
})

SUPPORT_INTENTS = frozenset({
    "faq_like",
    "support_query",
    "support",
    "faq",
    "troubleshooting",
})

OVERVIEW_FOCUS = (
    "Overview of {org_name}: cover what it is and the most important organization "
    "facts from the sources. Prefer substance over promotions and news. "
    "About {word_limit} words."
)

LISTING_FOCUS = "Use a concise list when helpful. Name source titles for distinct items."

SUPPORT_FOCUS = "Answer in a clear support style. Keep steps short when applicable."

GENERIC_FOCUS = "Stay focused and factual."


class CompactPromptBuilder:
    VERSION = PROMPT_TEMPLATE_VERSION

    @classmethod
    def build(
        cls,
        *,
        message: str,
        hits: list[SearchHit],
        built_context: BuiltContext | None,
        intent: str,
        settings,
        org_name: str = "the organization",
        speech_act_guidance: str | None = None,
    ) -> tuple[str, str]:
        # Qualify/refuse wording is applied post-generation (suffix / deterministic).
        _ = speech_act_guidance
        profile = get_mode_profile(settings)

        if built_context and built_context.prompt_text:
            context_block = built_context.prompt_text
        else:
            context_block = cls._format_hits(hits)

        system = cls.resolve_system_prompt(settings)
        task = cls._task_line(
            intent=intent,
            word_limit=profile.max_answer_words_overview,
            org_name=org_name,
            message=message,
        )
        user = (
            f"Sources:\n{context_block}\n\n"
            f"Task: {task}\n\n"
            f"Question: {message.strip()}\n\n"
            f"Answer:"
        )
        return system, user

    @classmethod
    def resolve_system_prompt(cls, settings) -> str:
        """Admin system prompt is the primary agent control surface."""
        custom = (getattr(settings, "system_prompt", None) or "").strip()
        return custom or DEFAULT_SYSTEM_PROMPT

    @classmethod
    def _task_line(
        cls,
        *,
        intent: str,
        word_limit: int,
        org_name: str,
        message: str,
    ) -> str:
        query_lang = detect_query_language(message)
        lang = (
            "Reply in natural Ukrainian."
            if query_lang == "uk"
            else "Reply in the same language as the question."
        )
        if intent in OVERVIEW_INTENTS:
            focus = OVERVIEW_FOCUS.format(org_name=org_name, word_limit=word_limit)
        elif intent in SUPPORT_INTENTS:
            focus = SUPPORT_FOCUS
        elif intent in LISTING_INTENTS:
            focus = LISTING_FOCUS
        else:
            focus = GENERIC_FOCUS
        return f"{focus} {lang}"

    @staticmethod
    def _format_hits(hits: list[SearchHit]) -> str:
        parts: list[str] = []
        seen: set[str] = set()
        for i, hit in enumerate(hits, start=1):
            url = (hit.url or "").strip()
            if url in seen:
                continue
            seen.add(url)
            title = hit.title or url
            snippet = (hit.text or "").strip()
            header = f"Source {i}: {title}\nURL: {url}"
            parts.append(f"{header}\n{snippet}")
        return "\n\n".join(parts)

    @staticmethod
    def truncate_prompts(system: str, user: str, max_prompt: int) -> tuple[str, str]:
        """Trim source content under budget; never drop Question/Answer anchors."""
        combined = len(system) + len(user) + 2
        if combined <= max_prompt:
            return system, user
        overflow = combined - max_prompt
        marker = "\n\nQuestion:"
        idx = user.rfind(marker)
        if idx >= 0:
            head = user[:idx]
            tail = user[idx:]
            # Prefer trimming Sources block; keep Task + Question when present.
            task_marker = "\n\nTask:"
            task_idx = head.rfind(task_marker)
            if task_idx >= 0:
                sources = head[:task_idx]
                task_part = head[task_idx:]
                keep = max(200, len(sources) - overflow)
                return system, sources[:keep].rstrip() + task_part + tail
            keep = max(200, len(head) - overflow)
            return system, head[:keep].rstrip() + tail
        return system, user[: max(200, len(user) - overflow)]

    @staticmethod
    def contains_debug_trace(text: str) -> bool:
        markers = ("trace_steps", "retrieval_debug", "score_breakdown", "===== DEBUG")
        lower = text.lower()
        return any(m.lower() in lower for m in markers)
