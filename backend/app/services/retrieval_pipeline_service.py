"""Multi-stage retrieval pipeline orchestrator."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.source import Source
from app.models.settings import Settings
from app.schemas.knowledge_profile import AppliedKnowledgeConfig, KnowledgeProfile
from app.services.canonical_source_service import CanonicalSourceService
from app.services.context_builder_service import BuiltContext, ContextBuilderService
from app.services.retrieval_engine.context_builder import RetrievalContextBuilder
from app.services.retrieval_engine.diagnostics_builder import DiagnosticsBuilder
from app.services.retrieval_engine.pipeline import DocumentFirstRetrievalPipeline
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.qdrant_service import QdrantService, SearchHit
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_engine.semantic_expansion import SemanticExpansionService
from app.services.retrieval_intent_service import (
    BROAD_RETRIEVAL_INTENTS,
    RetrievalIntentResult,
    RetrievalIntentService,
)
from app.services.settings_flags import setting_bool
from app.services.language_resolver_service import detect_query_language
from app.services.llm_mode_service import effective_generation_settings
from app.services.source_intelligence_router import SourceIntelligenceRouter
from app.services.trace_service import TraceBuilder

@dataclass
class RetrievalDiagnostics:
    intent: str = ""
    legacy_intent: str = ""
    matched_topic_key: str | None = None
    matched_topic_label: str | None = None
    matched_aliases: list[str] = field(default_factory=list)
    matched_patterns: list[str] = field(default_factory=list)
    answer_strategy: str = "generic"
    is_broad: bool = False
    expanded_queries: list[str] = field(default_factory=list)
    expanded_terms: list[str] = field(default_factory=list)
    category_boosts_applied: list[str] = field(default_factory=list)
    boost_document_types: list[str] = field(default_factory=list)
    deprioritize_document_types: list[str] = field(default_factory=list)
    boost_content_hints: list[str] = field(default_factory=list)
    candidate_pages: list[dict] = field(default_factory=list)
    reranked_pages: list[dict] = field(default_factory=list)
    broad_injected: list[str] = field(default_factory=list)
    candidate_count: int = 0
    final_chunk_count: int = 0
    context_length: int = 0
    prompt_length: int = 0
    prompt_diagnostics: dict | None = None
    source_profile_routing: str = ""
    selected_source_profiles: list[dict] = field(default_factory=list)
    rejected_candidates: list[dict] = field(default_factory=list)
    query_language: str = "unknown"
    excluded_language_duplicates: list[dict] = field(default_factory=list)
    selected_language_sources: list[str] = field(default_factory=list)
    context_preview: str = ""
    no_answer_reason: str | None = None
    retrieval_debug: dict | None = None
    expansion_rejected_terms: list[str] = field(default_factory=list)
    context_build_report: dict | None = None
    score_breakdowns: list[dict] = field(default_factory=list)

    context_text_sent: str = ""
    context_text_preview: str = ""
    polish_skip_reason: str = ""
    rejected_source_alternatives: list[dict] = field(default_factory=list)
    quality_metrics: dict | None = None
    retrieval_pipeline_stages: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "legacy_intent": self.legacy_intent,
            "matched_topic_key": self.matched_topic_key,
            "matched_topic_label": self.matched_topic_label,
            "matched_aliases": self.matched_aliases,
            "matched_patterns": self.matched_patterns,
            "answer_strategy": self.answer_strategy,
            "is_broad": self.is_broad,
            "expanded_queries": self.expanded_queries,
            "expanded_terms": self.expanded_terms,
            "category_boosts_applied": self.category_boosts_applied,
            "boost_document_types": self.boost_document_types,
            "deprioritize_document_types": self.deprioritize_document_types,
            "boost_content_hints": self.boost_content_hints,
            "candidate_pages": self.candidate_pages,
            "reranked_pages": self.reranked_pages,
            "broad_injected": self.broad_injected,
            "candidate_count": self.candidate_count,
            "final_chunk_count": self.final_chunk_count,
            "context_length": self.context_length,
            "prompt_length": self.prompt_length,
            "prompt_diagnostics": self.prompt_diagnostics,
            "context_preview": self.context_preview,
            "no_answer_reason": self.no_answer_reason,
            "retrieval_debug": self.retrieval_debug,
            "source_profile_routing": self.source_profile_routing,
            "selected_source_profiles": self.selected_source_profiles,
            "rejected_candidates": self.rejected_candidates,
            "query_language": self.query_language,
            "excluded_language_duplicates": self.excluded_language_duplicates,
            "selected_language_sources": self.selected_language_sources,
            "expansion_rejected_terms": self.expansion_rejected_terms,
            "context_build_report": self.context_build_report,
            "score_breakdowns": self.score_breakdowns,
            "context_text_sent": self.context_text_sent,
            "context_text_preview": self.context_text_preview,
            "rejected_source_alternatives": self.rejected_source_alternatives,
            "quality_metrics": self.quality_metrics,
            "retrieval_pipeline_stages": self.retrieval_pipeline_stages,
        }


@dataclass
class PipelineResult:
    hits: list[SearchHit]
    context: BuiltContext | None
    diagnostics: RetrievalDiagnostics
    intent_result: RetrievalIntentResult
    applied_config: AppliedKnowledgeConfig
    retrieval_ms: int = 0


class RetrievalPipelineService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        embedding_service: EmbeddingService,
        qdrant_service: QdrantService,
    ) -> None:
        self.db = db
        self.settings = settings
        self.embedding = embedding_service
        self.qdrant = qdrant_service

    def run(
        self,
        message: str,
        normalized: str,
        *,
        query_vector: list[float] | None = None,
        debug: bool = False,
        trace: TraceBuilder | None = None,
        profile: KnowledgeProfile | None = None,
    ) -> PipelineResult:
        s = self.settings
        profile = profile or KnowledgeProfileService.from_settings(s)
        diag = RetrievalDiagnostics()
        t0 = perf_counter()

        if setting_bool(s, "enable_intent_aware_retrieval"):
            intent_result = RetrievalIntentService.classify(
                message, normalized=normalized, profile=profile
            )
        else:
            intent_result = RetrievalIntentResult(
                intent="general_information",
                legacy_intent="unknown",
            )

        legacy_intent = intent_result.legacy_intent
        query_language = detect_query_language(message)
        diag.query_language = query_language
        diag.intent = intent_result.intent
        diag.legacy_intent = legacy_intent
        diag.is_broad = intent_result.is_broad

        applied = AppliedKnowledgeConfig(detected_intent=legacy_intent)
        applied.matched_intent_key = intent_result.intent
        applied.answer_strategy = intent_result.answer_strategy  # type: ignore[assignment]
        if intent_result.matched_topic:
            applied.matched_topic_key = intent_result.matched_topic.key
            applied.matched_topic_label = intent_result.matched_topic.label
        applied.matched_aliases = list(intent_result.matched_aliases or [])
        applied.matched_patterns = list(intent_result.matched_patterns or [])
        diag.matched_topic_key = applied.matched_topic_key
        diag.matched_topic_label = applied.matched_topic_label
        diag.matched_aliases = applied.matched_aliases
        diag.matched_patterns = applied.matched_patterns
        diag.answer_strategy = intent_result.answer_strategy

        max_exp = int(getattr(s, "max_semantic_expansions", 5) or 5)
        semantic = SemanticExpansionService(profile, max_expansions=max_exp)
        if s.enable_query_expansion:
            expansion = semantic.expand(normalized, intent_result=intent_result)
            diag.expanded_queries = expansion.variants
            diag.expanded_terms = expansion.terms
            diag.expansion_rejected_terms = expansion.rejected_terms
        else:
            diag.expanded_queries = [normalized]

        rule_cfg = KnowledgeProfileService.applied_config_for_intent(profile, legacy_intent)
        applied.boosted_document_types = rule_cfg.boosted_document_types
        applied.deprioritized_document_types = rule_cfg.deprioritized_document_types
        applied.boosted_content_hints = rule_cfg.boosted_content_hints
        applied.deprioritized_content_hints = rule_cfg.deprioritized_content_hints
        applied.query_expansions = diag.expanded_queries
        diag.boost_document_types = rule_cfg.boosted_document_types
        diag.deprioritize_document_types = rule_cfg.deprioritized_document_types
        diag.boost_content_hints = rule_cfg.boosted_content_hints

        candidate_count = getattr(s, "retrieval_candidate_count", None) or 30

        doc_pipeline = DocumentFirstRetrievalPipeline(
            self.db, s, self.embedding, self.qdrant
        )
        doc_result = doc_pipeline.run(
            query=message,
            normalized=normalized,
            intent_result=intent_result,
            profile=profile,
            query_vector=query_vector,
            expansion_terms=diag.expanded_terms if s.enable_query_expansion else None,
            query_language=query_language,
        )

        hits = list(doc_result.selected_hits)
        diag.retrieval_pipeline_stages = doc_result.pipeline_stages
        diag.quality_metrics = doc_result.quality_metrics.to_dict()
        diag.retrieval_debug = doc_result.chunk_debug
        diag.source_profile_routing = SourceIntelligenceRouter.route_intent(legacy_intent)
        diag.rejected_candidates = DiagnosticsBuilder.rejected_candidates(
            doc_result.rejected_documents
        )

        if (
            setting_bool(s, "enable_broad_question_mode", default=True)
            and (intent_result.is_broad or intent_result.intent in BROAD_RETRIEVAL_INTENTS)
        ):
            injected = self._inject_broad_pages(hits, profile)
            if injected:
                diag.broad_injected = [h.url for h in injected]
                hits = self._merge_hits(injected, hits)

        if setting_bool(s, "enable_canonical_source_selection"):
            hits = CanonicalSourceService.select_context(
                hits, legacy_intent, candidate_count, s, profile=profile
            )

        hits, lang_excluded = ContextBuilderService.dedupe_bilingual_hits_with_report(
            hits, query_language
        )
        diag.excluded_language_duplicates = lang_excluded

        all_doc_hits = [d.representative_chunk for d in doc_result.all_documents]
        diag.candidate_count = len(doc_result.all_documents)
        diag.candidate_pages = DiagnosticsBuilder.selected_candidates(
            doc_result.all_documents
        )
        eff = effective_generation_settings(s)
        final_k = min(s.top_k, eff["max_sources_in_prompt"])
        reranked = hits[: max(final_k * 3, final_k)]
        diag.rejected_source_alternatives = self._rejected_alternatives(
            all_doc_hits,
            hits[:final_k],
            doc_result.rejected_documents,
        )
        diag.selected_language_sources = [h.url for h in hits[:final_k]]
        diag.reranked_pages = DiagnosticsBuilder.selected_candidates(
            doc_result.selected_documents
        )
        diag.selected_source_profiles = self._profile_summary(hits[:final_k])
        diag.score_breakdowns = DiagnosticsBuilder.score_breakdowns(
            doc_result.selected_documents
        )

        context: BuiltContext | None = None
        if getattr(s, "enable_context_builder", True):
            max_chunks = getattr(s, "max_chunks_per_page", None) or 2
            ctx_builder = RetrievalContextBuilder(self.db)
            context, ctx_report = ctx_builder.build(
                reranked,
                settings=s,
                user_message=message,
                max_pages=eff["max_sources_in_prompt"],
                max_chunks_per_page=max_chunks,
            )
            diag.context_length = len(context.prompt_text)
            diag.context_preview = context.prompt_text[:1200]
            diag.context_text_sent = context.prompt_text
            diag.context_text_preview = context.prompt_text[:2000]
            diag.final_chunk_count = context.total_chunks
            diag.context_build_report = ctx_report.to_dict()
            flat_hits = ContextBuilderService.flatten_hits(context.blocks, reranked)
        else:
            flat_hits = hits[: max(1, final_k)]
            diag.final_chunk_count = len(flat_hits)

        diag.retrieval_ms = doc_result.retrieval_ms or int((perf_counter() - t0) * 1000)

        if trace:
            trace.query_intent = legacy_intent
            trace.expanded_queries = diag.expanded_queries

        return PipelineResult(
            hits=flat_hits,
            context=context,
            diagnostics=diag,
            intent_result=intent_result,
            applied_config=applied,
            retrieval_ms=int((perf_counter() - t0) * 1000),
        )

    def _inject_broad_pages(
        self,
        existing: list[SearchHit],
        profile: KnowledgeProfile,
    ) -> list[SearchHit]:
        """Inject canonical / overview-capable sources for broad queries (SI-driven)."""
        if self.db is None:
            return []
        existing_urls = {h.url for h in existing}
        existing_keys = {(h.source_id, h.chunk_index) for h in existing}

        stmt = (
            select(Chunk, Source)
            .join(Source, Source.id == Chunk.source_id)
            .where(
                or_(
                    Chunk.is_homepage.is_(True),
                    Source.canonical.is_(True),
                    Source.should_answer_company.is_(True),
                    Source.should_answer_general.is_(True),
                )
            )
            .order_by(
                Source.importance.desc(),
                Chunk.is_homepage.desc(),
                Chunk.chunk_index.asc(),
            )
            .limit(48)
        )
        rows = list(self.db.execute(stmt).all())
        injected: list[SearchHit] = []
        s = self.settings
        homepage_extra = s.homepage_boost_value if s.homepage_boost_enabled else 0.1

        for row, source in rows:
            if row.url in existing_urls and any(
                h.source_id == row.source_id for h in existing
            ):
                continue
            key = (row.source_id, row.chunk_index)
            if key in existing_keys:
                continue
            importance = int(getattr(source, "importance", 0) or 0)
            base = 0.48 + min(0.22, importance / 450.0)
            if row.is_homepage:
                base += homepage_extra
            if getattr(source, "canonical", False):
                base += 0.08
            if getattr(source, "should_answer_company", False):
                base += 0.06
            injected.append(
                SearchHit(
                    score=base,
                    source_id=row.source_id,
                    chunk_index=row.chunk_index,
                    title=row.title or row.url or "",
                    url=row.url or "",
                    source_type=row.source_type or "page",
                    text=row.text or "",
                    heading=row.heading or "",
                    is_homepage=bool(row.is_homepage),
                    is_structured_block=bool(row.is_structured_block),
                    content_type_hint=row.content_type_hint or "generic",
                    document_type=row.document_type or source.document_type or "generic_page",
                    dense_score=0.0,
                    lexical_score=0.35,
                    final_score=base,
                    is_canonical=bool(getattr(source, "canonical", False)),
                    selection_reason="broad_inject:source_intelligence",
                    page_role=getattr(source, "page_role", "") or "",
                    importance=importance,
                    content_quality=int(getattr(source, "content_quality", 0) or 0),
                    source_canonical=bool(getattr(source, "canonical", False)),
                )
            )
            existing_keys.add(key)
        return injected

    @staticmethod
    def _merge_hits(*groups: list[SearchHit]) -> list[SearchHit]:
        merged: dict[str, SearchHit] = {}
        for group in groups:
            for hit in group:
                key = f"{hit.source_id}:{hit.chunk_index}"
                prev = merged.get(key)
                if prev is None or (hit.final_score or hit.score) > (prev.final_score or prev.score):
                    merged[key] = hit
        out = list(merged.values())
        out.sort(key=lambda h: h.final_score or h.score, reverse=True)
        return out

    @staticmethod
    def _profile_summary(hits: list[SearchHit]) -> list[dict]:
        out: list[dict] = []
        seen: set[int] = set()
        for hit in hits:
            if hit.source_id in seen:
                continue
            seen.add(hit.source_id)
            out.append(
                {
                    "url": hit.url,
                    "title": hit.title,
                    "document_type": hit.document_type,
                    "page_role": getattr(hit, "page_role", ""),
                    "importance": getattr(hit, "importance", 0),
                    "content_quality": getattr(hit, "content_quality", 0),
                    "canonical": getattr(hit, "source_canonical", False),
                    "boilerplate_ratio": getattr(hit, "boilerplate_ratio", 0.0),
                    "summary": getattr(hit, "source_profile_summary", ""),
                    "why_selected": getattr(hit, "profile_routing_reason", "")
                    or getattr(hit, "selection_reason", ""),
                }
            )
        return out

    @staticmethod
    def _rejected_alternatives(
        all_hits: list[SearchHit],
        selected_hits: list[SearchHit],
        rejected_documents: list,
    ) -> list[dict]:
        selected_ids = {h.source_id for h in selected_hits}
        reject_reasons = {
            d.source_id: (d.why_rejected or d.ranking_reason or "not selected")
            for d in rejected_documents
        }
        alts: list[dict] = []
        seen: set[int] = set()
        for hit in sorted(all_hits, key=lambda h: h.final_score or h.score, reverse=True):
            if hit.source_id in selected_ids or hit.source_id in seen:
                continue
            seen.add(hit.source_id)
            alts.append(
                {
                    "url": hit.url,
                    "title": hit.title,
                    "document_type": hit.document_type,
                    "score": round(hit.final_score or hit.score, 4),
                    "why_not_selected": reject_reasons.get(
                        hit.source_id,
                        getattr(hit, "rejection_reason", None) or "lower_score_or_diversity",
                    ),
                }
            )
            if len(alts) >= 5:
                break
        return alts
