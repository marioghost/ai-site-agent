"""Compact prompt builder — single source of truth for generation instructions."""
from __future__ import annotations

from app.services.context_builder_service import BuiltContext
from app.services.language_resolver_service import detect_query_language
from app.services.llm_mode_service import get_mode_profile
from app.services.qdrant_service import SearchHit
from app.services.source_intelligence_constants import PROMPT_TEMPLATE_VERSION

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

# Production system prompt — English, positive, optimized for Qwen/Llama/Gemma.
# Intent-specific lines append once; settings.system_prompt is not prepended (avoids conflicts).
SYSTEM_CORE = (
    "You are this website's AI assistant.\n"
    "Sources are the only factual authority — treat them as evidence.\n"
    "Synthesize across sources into one coherent answer; never summarize page-by-page.\n"
    "Lead with the answer; add details next; keep qualifiers last.\n"
    "Prefer synthesis over extraction; rewrite naturally; never repeat the same fact.\n"
    "Ignore marketing, navigation, and boilerplate.\n"
    "Complete every sentence; never stop mid-thought.\n"
    "Answer the user, not the documents.\n"
    "Write in {lang_instruction}"
)

OVERVIEW_FOCUS = (
    "For this overview of {org_name}: cover what it is and the most important "
    "organization facts from the sources. Prefer substance over promotions and news. "
    "Stay within about {word_limit} words."
)

LISTING_FOCUS = "Use a concise list when it helps clarity. Name source titles for distinct items."

SUPPORT_FOCUS = "Answer directly in a clear support style. Keep steps short when applicable."

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
        # speech_act_guidance intentionally unused: qualify/refuse wording is
        # applied post-generation (suffix / deterministic replies) to avoid
        # duplicated hedging instructions in the system prompt.
        _ = speech_act_guidance
        query_lang = detect_query_language(message)
        profile = get_mode_profile(settings)

        if built_context and built_context.prompt_text:
            context_block = built_context.prompt_text
        else:
            context_block = cls._format_hits(hits)

        system = cls._system_prompt(
            query_lang=query_lang,
            intent=intent,
            word_limit=profile.max_answer_words_overview,
            org_name=org_name,
        )
        user = f"Sources:\n{context_block}\n\nQuestion: {message.strip()}\n\nAnswer:"
        return system, user

    @classmethod
    def _system_prompt(
        cls,
        *,
        query_lang: str,
        intent: str,
        word_limit: int,
        org_name: str,
    ) -> str:
        lang_instruction = (
            "natural Ukrainian."
            if query_lang == "uk"
            else "the same language as the user's question."
        )
        body = SYSTEM_CORE.format(lang_instruction=lang_instruction)
        if intent in OVERVIEW_INTENTS:
            focus = OVERVIEW_FOCUS.format(org_name=org_name, word_limit=word_limit)
        elif intent in SUPPORT_INTENTS:
            focus = SUPPORT_FOCUS
        elif intent in LISTING_INTENTS:
            focus = LISTING_FOCUS
        else:
            focus = GENERIC_FOCUS
        return f"{body}\n{focus}"

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
            sources = user[:idx]
            tail = user[idx:]
            keep = max(200, len(sources) - overflow)
            return system, sources[:keep].rstrip() + tail
        return system, user[: max(200, len(user) - overflow)]

    @staticmethod
    def contains_debug_trace(text: str) -> bool:
        markers = ("trace_steps", "retrieval_debug", "score_breakdown", "===== DEBUG")
        lower = text.lower()
        return any(m.lower() in lower for m in markers)
