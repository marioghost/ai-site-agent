"""Compact prompt builder — minimal instructions, maximum context budget."""
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
    "category_overview",
    "topic_overview",
})

SUPPORT_INTENTS = frozenset({
    "faq_like",
    "support_query",
    "support",
    "faq",
    "troubleshooting",
})

COMPACT_SYSTEM_BASE = (
    "Answer only from the provided sources. Do not invent facts. "
    "Ignore navigation and boilerplate."
)

OVERVIEW_ANSWER_TEMPLATE = (
    "{base} Write {lang_instruction} Max {word_limit} words. "
    "Give a factual overview using only supplied content."
)

LISTING_ANSWER_TEMPLATE = (
    "{base} Write {lang_instruction} Use a concise list when helpful. "
    "Cite source titles for each item."
)

SUPPORT_ANSWER_TEMPLATE = (
    "{base} Write {lang_instruction} Answer directly in support/FAQ style. "
    "Keep steps short when applicable."
)

GENERIC_ANSWER_TEMPLATE = "{base} Write {lang_instruction} Be concise and factual."


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
    ) -> tuple[str, str]:
        query_lang = detect_query_language(message)
        profile = get_mode_profile(settings)
        is_overview = intent in OVERVIEW_INTENTS

        if built_context and built_context.prompt_text:
            context_block = built_context.prompt_text
        else:
            context_block = cls._format_hits(hits)

        system = cls._system_prompt(
            query_lang=query_lang,
            intent=intent,
            is_overview=is_overview,
            word_limit=profile.max_answer_words_overview,
            org_name=org_name,
            custom=(settings.system_prompt or "").strip(),
            settings=settings,
        )
        user = f"Sources:\n{context_block}\n\nQuestion: {message.strip()}\n\nAnswer:"
        return system, user

    @classmethod
    def _system_prompt(
        cls,
        *,
        query_lang: str,
        intent: str,
        is_overview: bool,
        word_limit: int,
        org_name: str,
        custom: str,
        settings,
    ) -> str:
        lang_instruction = (
            "natural Ukrainian." if query_lang == "uk" else "the same language as the question."
        )
        base = COMPACT_SYSTEM_BASE
        if is_overview or intent in OVERVIEW_INTENTS:
            body = (
                f"{base} Write {lang_instruction} Max {word_limit} words. "
                f"Give a factual overview of {org_name} using only supplied content."
            )
        elif intent in SUPPORT_INTENTS:
            body = SUPPORT_ANSWER_TEMPLATE.format(
                base=base,
                lang_instruction=lang_instruction,
            )
        elif intent in LISTING_INTENTS:
            body = LISTING_ANSWER_TEMPLATE.format(
                base=base,
                lang_instruction=lang_instruction,
            )
        else:
            body = GENERIC_ANSWER_TEMPLATE.format(
                base=base,
                lang_instruction=lang_instruction,
            )

        profile = get_mode_profile(settings)
        if custom and profile.key != "fast":
            trimmed = custom[:400].strip()
            if trimmed:
                return f"{trimmed}\n{body}"
        return body

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
    def contains_debug_trace(text: str) -> bool:
        markers = ("trace_steps", "retrieval_debug", "score_breakdown", "===== DEBUG")
        lower = text.lower()
        return any(m.lower() in lower for m in markers)
