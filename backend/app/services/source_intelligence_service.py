"""Build and apply Source Intelligence profiles (domain-agnostic)."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse

from app.models.source import Source
from app.models.settings import Settings
from app.schemas.knowledge_profile import KnowledgeProfile
from app.schemas.source_intelligence import SourceSemanticProfile
from app.services.content_signals import is_homepage_url
from app.services.document_type_service import detect_document_type
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.source_semantic_rules import build_rules_semantic
from app.services.source_intelligence_llm_service import SourceIntelligenceLLMService
from app.services.settings_flags import setting_bool
from app.services.source_intelligence_constants import (
    CANONICAL_DOCUMENT_TYPES,
    DOCUMENT_TYPE_TO_ROLE,
    GENERIC_DOCUMENT_TYPES,
    LOW_OVERVIEW_DOCUMENT_TYPES,
    SOURCE_INTELLIGENCE_VERSION,
)
from app.services.rag_planning.purpose_catalog import role_from_purpose

from app.services.source_intelligence_perf import detect_source_language

_LANG_PATH_SEGMENTS = frozenset(
    {
        "en",
        "uk",
        "ua",
        "ru",
        "de",
        "fr",
        "es",
        "pl",
        "it",
        "pt",
        "en-us",
        "uk-ua",
        "ru-ru",
    }
)

_KEYWORD_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "are",
        "was",
        "were",
        "have",
        "has",
        "will",
        "can",
        "not",
        "you",
        "your",
        "our",
        "all",
        "any",
        "page",
        "home",
        "site",
        "http",
        "https",
        "www",
        "com",
        "html",
        "про",
        "для",
        "або",
        "також",
        "цього",
        "який",
        "яка",
        "які",
        "що",
        "як",
        "це",
        "на",
        "від",
        "при",
    }
)


@dataclass
class SourceProfile:
    source_id: int
    url: str
    document_type: str = "generic_page"
    page_role: str = "generic"
    importance: int = 50
    canonical: bool = False
    content_quality: int = 50
    boilerplate_ratio: float = 0.0
    site_section: str = "general"
    topics: list[str] = field(default_factory=list)
    entity_types: list[str] = field(default_factory=list)
    should_answer_general: bool = False
    should_answer_product: bool = False
    should_answer_support: bool = False
    should_answer_company: bool = False
    llm_summary: str = ""
    keywords: list[str] = field(default_factory=list)
    confidence: float = 0.5
    profile_version: str = SOURCE_INTELLIGENCE_VERSION
    source_language: str = "unknown"
    semantic: dict | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


def _url_depth(url: str) -> int:
    path = urlparse(url or "").path.strip("/")
    if not path:
        return 0
    return len([p for p in path.split("/") if p])


def _site_section(url: str, document_type: str) -> str:
    path = (urlparse(url or "").path or "").lower()
    for segment in path.strip("/").split("/"):
        if not segment or segment in _LANG_PATH_SEGMENTS:
            continue
        if len(segment) <= 1:
            continue
        return segment[:64]
    return document_type.replace("_page", "")[:64] or "general"


def _extract_keywords(title: str, main_text: str, limit: int = 12) -> list[str]:
    """Prefer title tokens, then frequent content tokens; drop stopwords."""
    title_tokens = re.findall(r"[\w\u0400-\u04FF]{3,}", (title or "").lower())
    body_tokens = re.findall(r"[\w\u0400-\u04FF]{3,}", (main_text or "")[:1200].lower())
    freq: dict[str, int] = {}
    for tok in body_tokens:
        if tok in _KEYWORD_STOP:
            continue
        freq[tok] = freq.get(tok, 0) + 1

    out: list[str] = []
    seen: set[str] = set()
    for tok in title_tokens:
        if tok in _KEYWORD_STOP or tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
        if len(out) >= max(4, limit // 2):
            break

    for tok, _count in sorted(freq.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0])):
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
        if len(out) >= limit:
            break
    return out


def _content_summary(title: str, main_text: str, *, max_chars: int = 280) -> str:
    """Page-specific lede summary — never role boilerplate."""
    text = (main_text or "").strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    pick = ""
    skip_prefixes = (
        "cookie",
        "©",
        "copyright",
        "all rights",
        "javascript",
        "enable cookies",
        "privacy policy",
    )
    for para in paragraphs:
        clean = re.sub(r"\s+", " ", para).strip()
        if len(clean) < 40:
            continue
        low = clean.lower()
        if any(low.startswith(p) or p in low[:40] for p in skip_prefixes):
            continue
        pick = clean
        break
    if not pick:
        pick = re.sub(r"\s+", " ", text)[:max_chars].strip()
    title_clean = (title or "").strip()
    if title_clean and pick:
        if title_clean.lower() not in pick.lower()[:120]:
            combined = f"{title_clean}. {pick}"
        else:
            combined = pick
    else:
        combined = pick or title_clean
    return combined[:max_chars].strip()


class SourceIntelligenceService:
    """Compute source profiles from generic signals + Knowledge Profile rules."""

    @staticmethod
    def build_profile(
        source: Source,
        profile: KnowledgeProfile | None = None,
        *,
        settings: Settings | None = None,
        use_llm: bool | None = None,
        db=None,
        stats=None,
    ) -> SourceProfile:
        profile = profile or KnowledgeProfileService.default_profile()
        url = source.url or ""
        title = source.title or ""
        main_text = source.main_content_text or source.extracted_text or ""
        is_home = is_homepage_url(url)
        document_type = source.document_type or detect_document_type(
            url=url,
            title=title,
            headings=main_text[:500],
            source_type=source.source_type or "page",
            profile=profile,
        )
        if document_type not in GENERIC_DOCUMENT_TYPES:
            document_type = "generic_page"
        if is_home:
            document_type = "homepage"

        page_role = DOCUMENT_TYPE_TO_ROLE.get(document_type, "generic")
        boilerplate_ratio = float(source.boilerplate_ratio or 0.0)
        main_chars = source.main_content_chars or len(main_text)
        url_depth = _url_depth(url)

        content_quality = SourceIntelligenceService._content_quality(
            main_chars=main_chars,
            boilerplate_ratio=boilerplate_ratio,
            title=title,
            main_text=main_text,
        )
        source_language = detect_source_language(title, main_text[:800])
        keywords = _extract_keywords(title, main_text)
        site_section = _site_section(url, document_type)

        semantic_profile: SourceSemanticProfile | None = None
        llm_enabled = use_llm
        if llm_enabled is None and settings is not None:
            llm_enabled = setting_bool(settings, "enable_llm_source_intelligence", default=True)
        if llm_enabled and settings is not None:
            semantic_profile = SourceIntelligenceLLMService.generate(
                source,
                settings,
                document_type=document_type,
                page_role=page_role,
                db=db,
                stats=stats,
            )
        if semantic_profile is None:
            semantic_profile = build_rules_semantic(
                source,
                page_role=page_role,
                document_type=document_type,
                keywords=keywords,
                site_section=site_section,
            )
        else:
            semantic_profile = SourceIntelligenceService._merge_semantic(
                semantic_profile,
                build_rules_semantic(
                    source,
                    page_role=page_role,
                    document_type=document_type,
                    keywords=keywords,
                    site_section=site_section,
                ),
            )

        # Refine page_role from high-confidence purpose (keeps type as weak prior).
        page_role = SourceIntelligenceService._refine_page_role(
            page_role=page_role,
            document_type=document_type,
            semantic=semantic_profile,
            is_homepage=is_home,
        )

        summary = _content_summary(title, main_text)
        if not summary and semantic_profile.main_topic:
            summary = semantic_profile.main_topic[:160]

        if semantic_profile.main_topic:
            topics = [semantic_profile.main_topic, *semantic_profile.subtopics[:6]]
        else:
            topics = semantic_profile.subtopics[:8]
        keywords = list(
            dict.fromkeys(
                keywords
                + semantic_profile.search_keywords
                + semantic_profile.synonyms
            )
        )[:24]

        confidence = min(0.98, 0.45 + content_quality / 200)
        if semantic_profile.confidence > confidence:
            confidence = semantic_profile.confidence

        canonical = SourceIntelligenceService._is_canonical(
            url=url,
            title=title,
            document_type=document_type,
            is_homepage=is_home,
            profile=profile,
            content_quality=content_quality,
            document_purpose=semantic_profile.document_purpose,
        )
        importance = SourceIntelligenceService._importance(
            document_type=document_type,
            page_role=page_role,
            canonical=canonical,
            is_homepage=is_home,
            url_depth=url_depth,
            content_quality=content_quality,
            boilerplate_ratio=boilerplate_ratio,
            main_chars=main_chars,
            profile=profile,
        )
        if canonical:
            confidence = min(0.98, confidence + 0.08)

        flags = SourceIntelligenceService._answer_flags(document_type, page_role)
        flags = SourceIntelligenceService._apply_semantic_flags(flags, semantic_profile)

        # Prefer semantic entity; never fall back to KP industry entity_type labels.
        entity_types = (
            [semantic_profile.entity_type] if semantic_profile.entity_type else []
        )

        return SourceProfile(
            source_id=source.id,
            url=url,
            document_type=document_type,
            page_role=page_role,
            importance=importance,
            canonical=canonical,
            content_quality=content_quality,
            boilerplate_ratio=boilerplate_ratio,
            site_section=site_section,
            topics=topics,
            entity_types=entity_types,
            should_answer_general=flags["general"],
            should_answer_product=flags["product"],
            should_answer_support=flags["support"],
            should_answer_company=flags["company"],
            llm_summary=summary,
            keywords=keywords,
            confidence=round(confidence, 3),
            source_language=source_language,
            semantic=semantic_profile.to_storage_dict(),
        )

    @staticmethod
    def _merge_semantic(
        primary: SourceSemanticProfile,
        fallback: SourceSemanticProfile,
    ) -> SourceSemanticProfile:
        data = fallback.model_dump()
        for key, value in primary.model_dump().items():
            if value in (None, "", [], 0.0):
                continue
            data[key] = value
        if primary.generator == "llm":
            data["generator"] = "hybrid"
        return SourceSemanticProfile.model_validate(data)

    @staticmethod
    def _refine_page_role(
        *,
        page_role: str,
        document_type: str,
        semantic: SourceSemanticProfile,
        is_homepage: bool,
    ) -> str:
        """Allow high-confidence purpose to correct weak/generic roles."""
        purpose = (semantic.document_purpose or "").lower().strip()
        purpose_conf = float(semantic.document_purpose_confidence or 0.0)
        if purpose_conf < 0.62 or not purpose:
            return page_role
        refined = role_from_purpose(purpose, fallback_role=page_role)
        # Homepage identity stays organization_overview even if purpose is landing page.
        if is_homepage or document_type == "homepage":
            if purpose in {"news", "promotion"}:
                return refined
            return "organization_overview"
        # Strong typed pages: only override when purpose clearly conflicts.
        strong_types = {
            "news_page",
            "blog_page",
            "blog_post",
            "promotion_page",
            "campaign_page",
            "offer_page",
            "action_page",
            "contact_page",
            "faq_page",
            "legal_page",
            "product_page",
            "pricing_page",
        }
        if document_type in strong_types:
            type_role = DOCUMENT_TYPE_TO_ROLE.get(document_type, page_role)
            incidental_purposes = {"news", "promotion", "contact information", "faq", "legal information"}
            if purpose in incidental_purposes:
                return refined
            return type_role
        if page_role in {"generic", "marketing"} or refined != page_role:
            return refined
        return page_role

    @staticmethod
    def _apply_semantic_flags(
        flags: dict[str, bool],
        semantic: SourceSemanticProfile,
    ) -> dict[str, bool]:
        purpose = semantic.document_purpose.lower()
        intents = {i.lower() for i in semantic.supported_intents}
        if purpose in {"product listing", "product details", "service description", "pricing"}:
            flags["product"] = True
        if purpose == "about company":
            flags["general"] = True
            flags["company"] = True
        if purpose == "landing page":
            # Landing pages are overview-capable only when suitable_for says so.
            suitable = " ".join(semantic.suitable_for).lower()
            if "overview" in suitable or "about" in suitable or "organization" in suitable:
                flags["general"] = True
                flags["company"] = True
        if purpose in {"faq", "support", "documentation"}:
            flags["support"] = True
        if purpose == "contact information":
            # Contact is not support documentation — keep company/general off.
            flags["support"] = False
            flags["general"] = False
            flags["company"] = False
        if purpose in {"news", "promotion"}:
            flags["general"] = False
            flags["company"] = False
        if "product_query" in intents or "listing" in intents:
            flags["product"] = True
        if "entity_overview" in intents or (
            "overview" in intents and purpose in {"about company", "landing page", "service description"}
        ):
            flags["general"] = True
        if "contacts_query" in intents or "contacts" in intents:
            # Contacts intent must not mark the page as support-answerable.
            flags["support"] = False
        return flags

    @staticmethod
    def _content_quality(
        *,
        main_chars: int,
        boilerplate_ratio: float,
        title: str,
        main_text: str,
    ) -> int:
        score = 40.0
        if main_chars >= 400:
            score += 15
        if main_chars >= 1200:
            score += 10
        if title.strip():
            score += 8
        if re.search(r"^#+\s|\n##\s", main_text):
            score += 5
        score -= boilerplate_ratio * 35
        if main_chars < 80:
            score -= 20
        # Penalize repetitive/nav-like token distributions.
        tokens = re.findall(r"[\w\u0400-\u04FF]{3,}", (main_text or "")[:2000].lower())
        if len(tokens) >= 40:
            unique_ratio = len(set(tokens)) / max(len(tokens), 1)
            if unique_ratio < 0.35:
                score -= 15
            elif unique_ratio < 0.5:
                score -= 8
        return max(5, min(100, int(score)))

    @staticmethod
    def _is_canonical(
        *,
        url: str,
        title: str,
        document_type: str,
        is_homepage: bool,
        profile: KnowledgeProfile,
        content_quality: int = 0,
        document_purpose: str = "",
    ) -> bool:
        purpose = (document_purpose or "").lower().strip()
        if purpose in {"news", "promotion", "contact information"}:
            return False
        quality = int(content_quality or 0)
        # Thin marketing homepages should not become default authority.
        if is_homepage:
            return quality >= 35
        if document_type in CANONICAL_DOCUMENT_TYPES:
            if document_type in LOW_OVERVIEW_DOCUMENT_TYPES:
                return False
            # About/company also need enough substance.
            return quality >= 35
        matched = KnowledgeProfileService.match_document_type(
            profile,
            url=url,
            title=title,
            headings="",
            is_homepage=is_homepage,
        )
        if matched in CANONICAL_DOCUMENT_TYPES:
            return quality >= 35
        return False

    @staticmethod
    def _importance(
        *,
        document_type: str,
        page_role: str,
        canonical: bool,
        is_homepage: bool,
        url_depth: int,
        content_quality: int,
        boilerplate_ratio: float,
        main_chars: int,
        profile: KnowledgeProfile,
    ) -> int:
        score = 35.0
        if is_homepage:
            score += 45
        elif document_type in {"about_page", "company_page"}:
            score += 38
        elif document_type in CANONICAL_DOCUMENT_TYPES:
            score += 22
        elif document_type in LOW_OVERVIEW_DOCUMENT_TYPES:
            score -= 18

        if canonical:
            score += 12
        score += content_quality * 0.25
        score -= boilerplate_ratio * 30
        score -= max(0, url_depth - 2) * 4
        if main_chars < 100:
            score -= 15

        for rule in profile.source_priority_rules:
            if rule.query_intent != "entity_overview":
                continue
            if document_type in rule.boost_document_types:
                idx = rule.boost_document_types.index(document_type)
                score += max(8, 18 - idx * 3)
            if document_type in rule.deprioritize_document_types:
                score -= 22

        if page_role in {"campaign", "news", "marketing"}:
            score -= 12
        if page_role == "contact":
            score -= 6
        return max(1, min(100, int(score)))

    @staticmethod
    def _answer_flags(document_type: str, page_role: str) -> dict[str, bool]:
        return {
            # generic alone is not overview-answerable — purpose flags may promote it.
            "general": page_role in {"organization_overview", "service_overview"}
            or document_type in {"homepage", "about_page", "company_page", "category_page"},
            "company": page_role == "organization_overview"
            or document_type in {"homepage", "about_page", "company_page"},
            "product": page_role in {"product_details", "service_overview", "pricing"}
            or document_type in {"product_page", "category_page", "service_page", "pricing_page"},
            "support": page_role in {"support", "faq", "documentation"}
            or document_type in {"faq_page", "support_page", "documentation_page", "knowledge_base_page"},
        }

    @staticmethod
    def apply_to_source(
        source: Source,
        sp: SourceProfile,
        *,
        settings=None,
        now=None,
    ) -> None:
        from app.services.source_intelligence_perf import (
            compute_llm_prompt_hash,
            compute_profile_settings_hash,
            llm_enabled_for_settings,
        )

        source.document_type = sp.document_type
        source.page_role = sp.page_role
        source.importance = sp.importance
        source.canonical = sp.canonical
        source.content_quality = sp.content_quality
        source.site_section = sp.site_section
        source.topics_json = json.dumps(sp.topics, ensure_ascii=False)
        source.entity_types_json = json.dumps(sp.entity_types, ensure_ascii=False)
        source.should_answer_general = sp.should_answer_general
        source.should_answer_product = sp.should_answer_product
        source.should_answer_support = sp.should_answer_support
        source.should_answer_company = sp.should_answer_company
        source.llm_summary = sp.llm_summary
        source.keywords_json = json.dumps(sp.keywords, ensure_ascii=False)
        source.profile_confidence = sp.confidence
        source.profile_version = sp.profile_version
        source.source_language = sp.source_language
        source.intelligence_json = json.dumps(sp.semantic or {}, ensure_ascii=False)
        source.needs_intelligence = False
        source.intelligence_content_hash = source.content_hash
        if settings is not None:
            source.intelligence_settings_hash = compute_profile_settings_hash(settings)
            if llm_enabled_for_settings(settings):
                source.intelligence_llm_model = settings.llm_model or ""
                source.intelligence_prompt_version = compute_llm_prompt_hash()
        if now is not None:
            source.intelligence_generated_at = now
            source.last_source_intelligence_at = now

    @staticmethod
    def profile_from_source(source: Source) -> SourceProfile | None:
        if not source.profile_version:
            return None
        try:
            topics = json.loads(source.topics_json or "[]")
        except json.JSONDecodeError:
            topics = []
        try:
            keywords = json.loads(source.keywords_json or "[]")
        except json.JSONDecodeError:
            keywords = []
        try:
            entity_types = json.loads(source.entity_types_json or "[]")
        except json.JSONDecodeError:
            entity_types = []
        semantic: dict | None = None
        try:
            raw_sem = json.loads(getattr(source, "intelligence_json", None) or "{}")
            if isinstance(raw_sem, dict) and raw_sem:
                semantic = raw_sem
        except json.JSONDecodeError:
            semantic = None
        return SourceProfile(
            source_id=source.id,
            url=source.url or "",
            document_type=source.document_type or "generic_page",
            page_role=getattr(source, "page_role", None) or "generic",
            importance=int(getattr(source, "importance", 0) or 0),
            canonical=bool(getattr(source, "canonical", False)),
            content_quality=int(getattr(source, "content_quality", 0) or 0),
            boilerplate_ratio=float(source.boilerplate_ratio or 0.0),
            site_section=getattr(source, "site_section", None) or "general",
            topics=topics if isinstance(topics, list) else [],
            entity_types=entity_types if isinstance(entity_types, list) else [],
            should_answer_general=bool(getattr(source, "should_answer_general", False)),
            should_answer_product=bool(getattr(source, "should_answer_product", False)),
            should_answer_support=bool(getattr(source, "should_answer_support", False)),
            should_answer_company=bool(getattr(source, "should_answer_company", False)),
            llm_summary=source.llm_summary or "",
            keywords=keywords if isinstance(keywords, list) else [],
            confidence=float(getattr(source, "profile_confidence", 0.5) or 0.5),
            profile_version=source.profile_version or "",
            source_language=getattr(source, "source_language", None) or "unknown",
            semantic=semantic,
        )

    @staticmethod
    def semantic_from_profile(sp: SourceProfile | None) -> SourceSemanticProfile | None:
        if sp is None or not sp.semantic:
            return None
        return SourceSemanticProfile.from_storage(sp.semantic)
