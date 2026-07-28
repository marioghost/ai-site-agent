"""Streaming RAG with full metadata parity to non-streaming /api/chat."""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from time import perf_counter

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.settings import Settings
from app.services.answer_cache_service import AnswerCacheService
from app.services.cache_namespace_service import build_retrieval_namespace
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.language_resolver_service import detect_query_language
from app.services.llm_call_tracker import LlmCallTracker
from app.services.llm_mode_service import effective_generation_settings, get_mode_profile
from app.services.llm_runtime_environment import collect_runtime_environment
from app.services.llm_options_service import estimate_tokens, resolve_llm_options
from app.services.llm_runtime_profiler import LlmRuntimeMetrics, compute_tokens_per_second
from app.services.model_warmup_service import ModelWarmupService
from app.services.ollama_service import OllamaError, OllamaService
from app.services.polish_policy_service import evaluate_polish, is_overview_intent
from app.services.query_intent_service import BROAD_INTENTS
from app.services.query_normalization_service import QueryNormalizationService
from app.services.response_validator_service import ResponseValidatorService
from app.services.retrieval_cache_service import CachedRetrievalResult, RetrievalCacheService
from app.services.retrieval_engine.prompt_builder import CompactPromptBuilder
from app.services.retrieval_pipeline_service import RetrievalPipelineService
from app.services.settings_flags import setting_bool
from app.services.source_formatting_service import SourceFormattingService
from app.services.chat_response_builder import ChatResponseBuilder, DiagnosticsCollector
from app.services.trace_service import TraceBuilder
from app.services.rag_service import (
    LLM_TIMEOUT_MESSAGE,
    CacheStatusInfo,
    RagResult,
    RagService,
    RagSource,
    _dict_to_hit,
    _hit_to_dict,
)
from app.services.qdrant_service import QdrantService, SearchHit
from app.schemas.knowledge_profile import AppliedKnowledgeConfig

logger = get_logger(__name__)


@dataclass
class _PreparedStream:
    message: str
    session_id: str | None
    request_id: str
    normalized: str
    expanded: list[str]
    fallback: str
    language: str
    fast: bool
    hits: list[SearchHit]
    pipeline_context: object | None
    pipeline_diagnostics: object | None
    query_intent: str
    applied_config: AppliedKnowledgeConfig
    retrieval_ms: int
    retrieval_debug: dict | None
    cache_hit: bool
    cache_type: str
    cache_info: CacheStatusInfo
    trace: TraceBuilder | None
    gen_system: str
    gen_user: str
    llm_opts: dict
    metrics: LlmRuntimeMetrics
    prompt_diagnostics: dict
    mode_profile: object
    user_ip: str | None
    user_agent: str | None
    referrer: str | None
    query_vector: list[float] | None
    kv: int
    bypass_cache: bool
    debug: bool
    qualify_suffix: str | None = None
    speech_language_diag: dict | None = None
    apply_speech_acts: bool = False


class RagStreamingService:
    def __init__(self, rag: RagService) -> None:
        self.rag = rag
        self.db: Session = rag.db
        self.settings: Settings = rag.settings
        self.ollama: OllamaService = rag.ollama
        self.embedding_service: EmbeddingService = rag.embedding_service
        self.qdrant_service: QdrantService = rag.qdrant_service
        self.retrieval_cache = rag.retrieval_cache
        self.answer_cache = rag.answer_cache
        self.polisher = rag.polisher
        self.builder = ChatResponseBuilder(self.settings)

    def iter_events(
        self,
        message: str,
        session_id: str | None,
        *,
        request_id: str,
        collector: DiagnosticsCollector | None = None,
        user_ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
        debug: bool = False,
        bypass_cache: bool = False,
        pipeline_provider=None,
        apply_speech_acts: bool = False,
    ) -> Iterator[tuple[str, dict]]:
        collector = collector or DiagnosticsCollector(
            request_id=request_id,
            session_id=session_id or "",
        )
        message_id = f"{request_id}-assistant"
        yield (
            "start",
            {
                "request_id": request_id,
                "session_id": session_id or "",
                "message_id": message_id,
                "streaming": True,
            },
        )
        collector.status("receive_request", "completed")

        try:
            yield ("status", collector.status("retrieval", "running"))
            prepared, early = self._prepare(
                message,
                session_id,
                request_id,
                user_ip,
                user_agent,
                referrer,
                debug,
                bypass_cache,
                pipeline_provider=pipeline_provider,
                apply_speech_acts=apply_speech_acts,
            )
            if (
                prepared.pipeline_diagnostics is not None
                and getattr(prepared.pipeline_diagnostics, "retrieval_pipeline_stages", None)
            ):
                collector.merge_retrieval_stages(
                    prepared.pipeline_diagnostics.retrieval_pipeline_stages
                )
            yield (
                "status",
                collector.status("retrieval", "completed", duration_ms=prepared.retrieval_ms),
            )
        except Exception as exc:  # noqa: BLE001
            yield (
                "error",
                {
                    "error_type": "prepare_error",
                    "message": str(exc),
                    "partial_response": None,
                    "partial_diagnostics": {"pipeline_stages": collector.stages},
                },
            )
            return

        if early is not None:
            yield from self._emit_cached_or_fallback(
                early, prepared, collector, user_ip, user_agent, referrer
            )
            return

        sources = self._format_sources(prepared.hits)
        retrieval_debug = self._merge_retrieval_debug(prepared)
        trace_dict = None
        if prepared.trace and self.settings.enable_tracing:
            trace_dict = prepared.trace.to_trace_dict()

        yield (
            "retrieval",
            {
                "sources": [asdict(s) for s in sources],
                "retrieval_debug": retrieval_debug,
                "trace_partial": trace_dict,
                "used_context": bool(prepared.hits),
                "cache_hit": prepared.cache_hit,
                "cache_type": prepared.cache_type,
            },
        )
        yield (
            "sources.completed",
            {
                "sources": [asdict(s) for s in sources],
                "count": len(sources),
            },
        )
        yield ("status", collector.status("context_building", "running"))
        yield ("status", collector.status("context_building", "completed"))

        collector.set_prompt_diagnostics(prepared.prompt_diagnostics)
        yield (
            "diagnostics",
            {
                "prompt_diagnostics": prepared.prompt_diagnostics,
                "timing_partial": collector.partial_timing(
                    retrieval_ms=prepared.retrieval_ms,
                    generation_ms=0,
                    polish_ms=0,
                    total_ms=prepared.retrieval_ms,
                ),
            },
        )

        if prepared.trace:
            prepared.trace.begin("llm_generation")
        yield ("status", collector.status("generation", "running"))

        t_gen = perf_counter()
        first_token_ms: int | None = None
        parts: list[str] = []
        stream_stats = None
        call_tracker = LlmCallTracker()
        env = collect_runtime_environment()
        try:
            for chunk in self.ollama.chat_stream(
                model=self.settings.llm_model,
                system_prompt=prepared.gen_system,
                user_prompt=prepared.gen_user,
                temperature=prepared.llm_opts["temperature"],
                max_tokens=prepared.llm_opts["num_predict"],
                num_ctx=prepared.llm_opts["num_ctx"],
                top_p=prepared.llm_opts.get("top_p"),
                repeat_penalty=prepared.llm_opts.get("repeat_penalty"),
                timeout=float(
                    prepared.llm_opts.get("generation_timeout_seconds")
                    or self.settings.ollama_generation_timeout_seconds
                    or 45
                ),
                keep_alive=prepared.llm_opts.get("keep_alive"),
            ):
                if chunk.text:
                    if first_token_ms is None:
                        first_token_ms = int((perf_counter() - t_gen) * 1000)
                        yield (
                            "llm.first_token",
                            {"time_to_first_token_ms": first_token_ms},
                        )
                    parts.append(chunk.text)
                    yield ("token", {"delta": chunk.text, "text": chunk.text})
                if chunk.done and chunk.stats:
                    stream_stats = chunk.stats
                    call_tracker.record("rag_generation_stream")
        except OllamaError as exc:
            if prepared.trace:
                prepared.trace.end("llm_generation", status="error", details={"error": str(exc)})
            generation_ms = int((perf_counter() - t_gen) * 1000)
            is_timeout = "timeout" in str(exc).lower()
            err_type = "llm_timeout" if is_timeout else "llm_error"
            yield (
                "error",
                {
                    "error_type": err_type,
                    "message": str(exc),
                    "partial_response": None,
                    "partial_diagnostics": {
                        **prepared.prompt_diagnostics,
                        "generation_ms": generation_ms,
                        "time_to_first_token_ms": first_token_ms,
                        "pipeline_stages": collector.stages,
                    },
                },
            )
            result = RagResult(
                answer=LLM_TIMEOUT_MESSAGE if is_timeout else prepared.fallback,
                sources=sources if is_timeout else [],
                used_context=bool(prepared.hits),
                request_id=request_id,
                cache_hit=prepared.cache_hit,
                cache_type=prepared.cache_type,
                retrieval_ms=prepared.retrieval_ms,
                generation_ms=generation_ms,
                retrieval_debug=prepared.retrieval_debug,
                retrieval_diagnostics=(
                    prepared.pipeline_diagnostics.to_dict()
                    if prepared.pipeline_diagnostics
                    else None
                ),
                query_intent=prepared.query_intent,
                applied_knowledge_config=prepared.applied_config.model_dump(),
                cache=prepared.cache_info,
                error_type=err_type,
                prompt_diagnostics=prepared.prompt_diagnostics,
            )
            finalized = self.rag._finalize(
                result,
                message,
                session_id,
                prepared.trace,
                user_ip,
                user_agent,
                referrer,
                prepared.normalized,
                prepared.expanded,
            )
            yield (
                "final",
                self._final_event(
                    finalized,
                    session_id,
                    request_id,
                    user_ip,
                    user_agent,
                    referrer,
                    debug=prepared.debug,
                ),
            )
            return

        answer = "".join(parts)
        generation_ms = int((perf_counter() - t_gen) * 1000)
        prepared.metrics.streaming_enabled = True
        prepared.metrics.model_status = ModelWarmupService.get_status(self.settings.llm_model)
        if stream_stats:
            prepared.metrics.apply_ollama_stats(
                stream_stats,
                first_token_ms=first_token_ms,
                generation_ms=generation_ms,
                gpu_visible=bool(env.get("nvidia_gpu_visible")),
            )
        else:
            out_tokens = max(1, len(answer) // 4)
            prepared.metrics.time_to_first_token_ms = first_token_ms
            prepared.metrics.generation_ms = generation_ms
            prepared.metrics.total_tokens_out = out_tokens
            prepared.metrics.tokens_per_second = compute_tokens_per_second(out_tokens, generation_ms)
        prepared.metrics.apply_call_tracker(call_tracker)
        prepared.prompt_diagnostics.update(prepared.metrics.to_dict())

        if prepared.trace:
            prepared.trace.end("llm_generation", details={"chars": len(answer)})

        context_text = (
            prepared.pipeline_context.prompt_text
            if prepared.pipeline_context and hasattr(prepared.pipeline_context, "prompt_text")
            else ""
        )
        validation = ResponseValidatorService(
            max_words=prepared.mode_profile.max_answer_words_overview + 40,
        ).validate(
            answer,
            query=message,
            context_text=context_text,
            is_overview=prepared.query_intent in BROAD_INTENTS,
        )
        if validation.applied_fixes:
            answer = validation.cleaned_answer
        if validation.warnings:
            prepared.prompt_diagnostics["validation_warnings"] = validation.warnings

        polish_ms = 0
        polish_decision = evaluate_polish(
            self.settings,
            answer=answer,
            language=prepared.language,
            fast_mode=prepared.fast,
            generation_ms=generation_ms,
            is_overview=is_overview_intent(prepared.query_intent),
        )
        prepared.prompt_diagnostics["polish_skip_reason"] = polish_decision.reason
        if polish_decision.enabled:
            if prepared.trace:
                prepared.trace.begin("ukrainian_polish")
            t_pol = perf_counter()
            call_tracker.record("ukrainian_polish")
            polish_model = (getattr(self.settings, "polish_model", None) or "").strip() or self.settings.llm_model
            answer = self.polisher.polish(
                answer,
                model=polish_model,
                temperature=self.settings.temperature,
                max_tokens=min(int(self.settings.max_tokens or 512), 512),
                timeout=float(getattr(self.settings, "polish_timeout_seconds", 15) or 15),
            )
            polish_ms = int((perf_counter() - t_pol) * 1000)
            prepared.prompt_diagnostics["polish_ms"] = polish_ms
            if prepared.trace:
                prepared.trace.end("ukrainian_polish")
        elif prepared.trace:
            prepared.trace.skip("ukrainian_polish", polish_decision.reason)
        prepared.prompt_diagnostics["polish_enabled"] = polish_ms > 0
        prepared.metrics.apply_call_tracker(call_tracker)
        prepared.prompt_diagnostics.update(call_tracker.to_dict())

        if prepared.qualify_suffix:
            from app.services.language.speech_act_render import apply_qualify_suffix

            before = answer
            answer = apply_qualify_suffix(answer, prepared.qualify_suffix)
            if answer != before:
                delta = (
                    answer[len(before) :]
                    if answer.startswith(before)
                    else f"\n\n{prepared.qualify_suffix}"
                )
                yield ("token", {"delta": delta, "text": delta})

        if prepared.trace:
            prepared.trace.begin("source_formatting")
            prepared.trace.end("source_formatting", details={"sources": len(sources)})
            prepared.trace.begin("response_returned")
            prepared.trace.end("response_returned")

        total_ms = prepared.retrieval_ms + generation_ms + polish_ms
        result = RagResult(
            answer=answer,
            sources=sources,
            used_context=True,
            request_id=request_id,
            cache_hit=prepared.cache_hit,
            cache_type=prepared.cache_type if prepared.cache_hit else "none",
            retrieval_ms=prepared.retrieval_ms,
            generation_ms=generation_ms,
            polish_ms=polish_ms,
            total_ms=total_ms,
            retrieval_debug=prepared.retrieval_debug,
            retrieval_diagnostics=(
                prepared.pipeline_diagnostics.to_dict() if prepared.pipeline_diagnostics else None
            ),
            query_intent=prepared.query_intent,
            applied_knowledge_config=prepared.applied_config.model_dump(),
            cache=prepared.cache_info,
            prompt_diagnostics=prepared.prompt_diagnostics,
            reasoning_diagnostics=prepared.speech_language_diag,
        )

        if (
            self.settings.enable_semantic_answer_cache
            and prepared.query_vector is not None
            and not prepared.bypass_cache
        ):
            try:
                self.answer_cache.store(
                    normalized_query=prepared.normalized,
                    query_text=message,
                    query_vector=prepared.query_vector,
                    answer_text=answer,
                    sources_json=json.dumps([asdict(src) for src in sources], ensure_ascii=False),
                    knowledge_version=prepared.kv,
                    ttl_seconds=self.settings.answer_cache_ttl_seconds,
                    namespace=build_retrieval_namespace(
                        self.settings,
                        db=self.db,
                        speech_acts_active=prepared.apply_speech_acts,
                    ),
                    used_context=True,
                    fallback_answer=prepared.fallback,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to store answer cache after stream: %s", exc)

        finalized = self.rag._finalize(
            result,
            message,
            session_id,
            prepared.trace,
            user_ip,
            user_agent,
            referrer,
            prepared.normalized,
            prepared.expanded,
        )

        yield ("status", collector.status("generation", "completed", duration_ms=generation_ms))
        collector.set_prompt_diagnostics(finalized.prompt_diagnostics)
        yield (
            "diagnostics",
            {
                "prompt_diagnostics": finalized.prompt_diagnostics,
                "timing_partial": collector.partial_timing(
                    retrieval_ms=finalized.retrieval_ms,
                    generation_ms=finalized.generation_ms,
                    polish_ms=finalized.polish_ms,
                    total_ms=finalized.total_ms,
                ),
            },
        )
        yield (
            "final",
            self._final_event(
                finalized,
                session_id,
                request_id,
                user_ip,
                user_agent,
                referrer,
                debug=prepared.debug,
            ),
        )

    def _final_event(
        self,
        result: RagResult,
        session_id: str | None,
        request_id: str,
        user_ip: str | None,
        user_agent: str | None,
        referrer: str | None,
        *,
        debug: bool = False,
    ) -> dict:
        response = self.builder.from_rag_result(
            result,
            request_id=request_id,
            session_id=session_id or "",
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
            debug=debug,
        )
        return self.builder.final_event_payload(response)

    def _emit_cached_or_fallback(
        self,
        result: RagResult,
        prepared: _PreparedStream,
        collector: DiagnosticsCollector,
        user_ip: str | None,
        user_agent: str | None,
        referrer: str | None,
    ) -> Iterator[tuple[str, dict]]:
        sources = result.sources
        retrieval_debug = self._merge_retrieval_debug(prepared, result)
        trace_dict = result.trace
        yield (
            "retrieval",
            {
                "sources": [asdict(s) for s in sources],
                "retrieval_debug": retrieval_debug,
                "trace_partial": trace_dict,
                "used_context": result.used_context,
                "cache_hit": result.cache_hit,
                "cache_type": result.cache_type,
            },
        )
        if result.answer:
            yield ("token", {"delta": result.answer, "text": result.answer})
        finalized = self.rag._finalize(
            result,
            prepared.message,
            prepared.session_id,
            prepared.trace,
            prepared.user_ip,
            prepared.user_agent,
            prepared.referrer,
            prepared.normalized,
            prepared.expanded,
        )
        collector.set_prompt_diagnostics(finalized.prompt_diagnostics)
        yield ("status", collector.status("generation", "completed", duration_ms=finalized.generation_ms))
        yield (
            "final",
            self._final_event(
                finalized,
                prepared.session_id,
                prepared.request_id,
                user_ip,
                user_agent,
                referrer,
                debug=prepared.debug,
            ),
        )

    def _merge_retrieval_debug(self, prepared: _PreparedStream, result: RagResult | None = None) -> dict | None:
        if result:
            return ChatResponseBuilder.build_retrieval_debug(result)
        if not prepared.retrieval_debug and not prepared.pipeline_diagnostics:
            return None
        payload: dict = dict(prepared.retrieval_debug or {})
        if prepared.pipeline_diagnostics:
            payload.update(prepared.pipeline_diagnostics.to_dict())
        if prepared.cache_info:
            payload["cache"] = asdict(prepared.cache_info)
        if prepared.prompt_diagnostics:
            payload["prompt_diagnostics"] = prepared.prompt_diagnostics
        return payload or None

    def _format_sources(self, hits: list[SearchHit]) -> list[RagSource]:
        s = self.settings
        if not (s.enable_source_links and s.enable_sources):
            return []
        return [
            RagSource(title=fs.title, url=fs.url, source_type=fs.source_type, score=fs.score)
            for fs in SourceFormattingService.format(hits)
        ]

    def _prepare(
        self,
        message: str,
        session_id: str | None,
        request_id: str,
        user_ip: str | None,
        user_agent: str | None,
        referrer: str | None,
        debug: bool,
        bypass_cache: bool,
        pipeline_provider=None,
        apply_speech_acts: bool = False,
    ) -> tuple[_PreparedStream, RagResult | None]:
        s = self.settings
        fallback = s.fallback_answer or "Я не знайшов цієї інформації на сайті."
        cache_info = CacheStatusInfo(bypassed=bypass_cache)
        trace = TraceBuilder(request_id) if s.enable_tracing else None
        if trace:
            trace.begin("receive_request", {"session_id": session_id})
            trace.end("receive_request", details={"message_length": len(message)})

        profile = KnowledgeProfileService.from_settings(s)
        applied_config = AppliedKnowledgeConfig()
        query_intent = "unknown"
        pipeline_context = None
        pipeline_diagnostics = None
        normalized = QueryNormalizationService.normalize(message)
        if trace:
            trace.begin("normalize_query")
            trace.normalized_query = normalized
            trace.end("normalize_query", details={"normalized": normalized})
        expanded = [normalized]
        if trace:
            trace.skip("query_expansion", "delegated_to_pipeline")
            trace.skip("query_intent", "delegated_to_pipeline")

        kv = s.knowledge_version or 1
        cache_namespace = build_retrieval_namespace(
            s, db=self.db, speech_acts_active=apply_speech_acts
        )
        cache_info.invalidation_version = cache_namespace.get("index_version")
        cache_info.cache_namespace = cache_namespace
        if trace:
            trace.knowledge_version = kv
            trace.retrieval_mode = s.retrieval_mode or "hybrid"

        language = detect_query_language(message)
        if language == "unknown":
            language = (s.default_response_language or "uk").lower()
        eff = effective_generation_settings(s)
        fast = eff["llm_mode_profile"] == "fast" or bool(s.fast_mode_enabled)
        top_k = min(s.top_k, eff["max_sources_in_prompt"]) if fast else s.top_k
        query_vector: list[float] | None = None
        retrieval_ms = 0
        retrieval_debug: dict | None = None
        all_hits: list[SearchHit] = []

        if s.enable_semantic_answer_cache and not bypass_cache:
            if trace:
                trace.begin("semantic_answer_cache_lookup")
            try:
                query_vector = self.embedding_service.embed_query(normalized)
                cached = self.answer_cache.lookup(
                    query_vector,
                    kv,
                    s.semantic_cache_similarity_threshold,
                    namespace=cache_namespace,
                    fallback_answer=fallback,
                )
                if cached is not None:
                    if trace:
                        trace.end("semantic_answer_cache_lookup", details={"hit": True})
                    cache_info.answer_cache_hit = True
                    cache_info.cache_type = cached.cache_type or "answer_success"
                    sources = [RagSource(**src) for src in json.loads(cached.sources_json or "[]")]
                    early = RagResult(
                        answer=cached.answer_text,
                        sources=sources,
                        used_context=cached.used_context,
                        request_id=request_id,
                        cache_hit=True,
                        cache_type=cache_info.cache_type,
                        cache=cache_info,
                    )
                    prep = _PreparedStream(
                        message=message,
                        session_id=session_id,
                        request_id=request_id,
                        normalized=normalized,
                        expanded=expanded,
                        fallback=fallback,
                        language=language,
                        fast=fast,
                        hits=[],
                        pipeline_context=None,
                        pipeline_diagnostics=None,
                        query_intent=query_intent,
                        applied_config=applied_config,
                        retrieval_ms=0,
                        retrieval_debug=None,
                        cache_hit=True,
                        cache_type=cache_info.cache_type,
                        cache_info=cache_info,
                        trace=trace,
                        gen_system="",
                        gen_user="",
                        llm_opts={},
                        metrics=LlmRuntimeMetrics(),
                        prompt_diagnostics={},
                        mode_profile=get_mode_profile(s),
                        user_ip=user_ip,
                        user_agent=user_agent,
                        referrer=referrer,
                        query_vector=query_vector,
                        kv=kv,
                        bypass_cache=bypass_cache,
                        debug=debug,
                        apply_speech_acts=apply_speech_acts,
                    )
                    return prep, early
                if trace:
                    trace.end("semantic_answer_cache_lookup", details={"hit": False})
            except Exception as exc:  # noqa: BLE001
                if trace:
                    trace.end("semantic_answer_cache_lookup", status="error", details={"error": str(exc)})
                logger.warning("Answer-cache lookup failed (stream): %s", exc)
        elif trace:
            trace.skip(
                "semantic_answer_cache_lookup",
                "disabled" if not s.enable_semantic_answer_cache else "bypassed",
            )

        cache_hit = False
        cache_type = "none"
        rerank_enabled = bool(s.enable_reranking)
        retr_key = RetrievalCacheService.make_key(
            normalized_query=normalized,
            namespace=cache_namespace,
            top_k=top_k,
            similarity_threshold=float(s.similarity_threshold or 0.55),
            qdrant_collection=s.qdrant_collection,
            rerank_enabled=rerank_enabled,
            query_intent=query_intent if setting_bool(s, "enable_intent_aware_retrieval") else "",
        )
        cache_info.cache_key = retr_key
        hits: list[SearchHit] | None = None

        if s.enable_retrieval_cache and not bypass_cache:
            if trace:
                trace.begin("retrieval_cache_lookup")
            try:
                cached_retrieval = self.retrieval_cache.get(retr_key, knowledge_version=kv, namespace=cache_namespace)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Retrieval cache lookup error (stream): %s", exc)
                cached_retrieval = None
            if cached_retrieval is not None:
                hits = [_dict_to_hit(c) for c in cached_retrieval.chunks]
                cache_hit = True
                cache_type = cached_retrieval.cache_type
                cache_info.retrieval_cache_hit = True
                cache_info.cache_type = cache_type
                cache_info.cache_age_seconds = cached_retrieval.age_seconds
                cache_info.cache_ttl_seconds = cached_retrieval.ttl_seconds
                cache_info.cached_selected_chunk_count = cached_retrieval.selected_chunks_count
                cache_info.cached_context_used = cached_retrieval.context_used
                cache_info.negative_cache = cached_retrieval.negative_cache
                if trace:
                    trace.end("retrieval_cache_lookup", details={"hit": True, "chunks": len(hits)})
            elif trace:
                trace.end("retrieval_cache_lookup", details={"hit": False})
        elif trace:
            trace.skip("retrieval_cache_lookup", "disabled" if not s.enable_retrieval_cache else "bypassed")

        if hits is None:
            t_retr = perf_counter()
            if pipeline_provider is not None:
                pipe_result = pipeline_provider(
                    message,
                    normalized,
                    query_vector=query_vector,
                    debug=debug,
                    trace=trace,
                    profile=profile,
                )
            else:
                pipeline = RetrievalPipelineService(self.db, s, self.embedding_service, self.qdrant_service)
                if query_vector is None:
                    query_vector = self.embedding_service.embed_query(normalized)
                pipe_result = pipeline.run(
                    message,
                    normalized,
                    query_vector=query_vector,
                    debug=debug,
                    trace=trace,
                    profile=profile,
                )
            query_intent = pipe_result.intent_result.legacy_intent
            applied_config = pipe_result.applied_config
            expanded = pipe_result.diagnostics.expanded_queries or expanded
            all_hits = pipe_result.hits
            hits = pipe_result.hits
            retrieval_debug = pipe_result.diagnostics.retrieval_debug
            if pipe_result.diagnostics.retrieval_debug is None and debug:
                retrieval_debug = pipe_result.diagnostics.to_dict()
            retrieval_ms = int((perf_counter() - t_retr) * 1000)
            pipeline_context = pipe_result.context
            pipeline_diagnostics = pipe_result.diagnostics
            if trace and s.enable_reranking:
                trace.begin("reranking")
                trace.end("reranking", details={"count": len(hits)})
            if s.enable_retrieval_cache and hits and not bypass_cache:
                self.retrieval_cache.store(
                    cache_key=retr_key,
                    normalized_query=normalized,
                    knowledge_version=kv,
                    namespace=cache_namespace,
                    chunks=[_hit_to_dict(h) for h in hits],
                    ttl_seconds=s.retrieval_cache_ttl_seconds,
                    cache_type="retrieval_success",
                )
            if trace and all_hits:
                trace.set_chunks(all_hits, {h.url for h in hits})

        applied_config_dict = applied_config.model_dump() if applied_config else None
        speech_plan = None
        speech_language_diag = None
        qualify_suffix = None
        if apply_speech_acts:
            from app.services.language.speech_act_decide import decision_from_retrieval
            from app.services.language.speech_act_render import (
                plan_speech_act_render,
                speech_act_diagnostics,
            )
            from app.services.reasoning.types import REASONING_PATH_SERVICE

            assessment, decision = decision_from_retrieval(
                hits=hits or [],
                query_intent=query_intent,
                applied_knowledge_config=applied_config_dict,
                used_context=bool(hits),
            )
            speech_plan = plan_speech_act_render(
                decision,
                query_language=language,
                default_language=s.default_response_language or "uk",
            )
            speech_language_diag = speech_act_diagnostics(
                speech_plan,
                decision=decision,
                assessment_diagnostics=assessment.to_diagnostics(),
                reasoning_path=REASONING_PATH_SERVICE,
            )
            qualify_suffix = speech_plan.qualify_suffix
            if speech_plan.skip_llm:
                if trace:
                    trace.skip("context_building", "speech_act_deterministic")
                    trace.skip("llm_generation", "speech_act_skip_llm")
                early = RagResult(
                    answer=speech_plan.text or fallback,
                    sources=[],
                    used_context=False,
                    request_id=request_id,
                    cache_hit=cache_hit,
                    cache_type=cache_type if cache_hit else "none",
                    retrieval_ms=retrieval_ms,
                    generation_ms=0,
                    retrieval_debug=retrieval_debug,
                    query_intent=query_intent,
                    applied_knowledge_config=applied_config_dict,
                    cache=cache_info,
                    prompt_diagnostics={
                        "llm_skipped": True,
                        "deterministic_response_used": True,
                        "language_instruction": speech_plan.language_instruction,
                    },
                    reasoning_diagnostics=speech_language_diag,
                )
                prep = _PreparedStream(
                    message=message,
                    session_id=session_id,
                    request_id=request_id,
                    normalized=normalized,
                    expanded=expanded,
                    fallback=fallback,
                    language=language,
                    fast=fast,
                    hits=hits or [],
                    pipeline_context=pipeline_context,
                    pipeline_diagnostics=pipeline_diagnostics,
                    query_intent=query_intent,
                    applied_config=applied_config,
                    retrieval_ms=retrieval_ms,
                    retrieval_debug=retrieval_debug,
                    cache_hit=cache_hit,
                    cache_type=cache_type,
                    cache_info=cache_info,
                    trace=trace,
                    gen_system="",
                    gen_user="",
                    llm_opts={},
                    metrics=LlmRuntimeMetrics(),
                    prompt_diagnostics=early.prompt_diagnostics or {},
                    mode_profile=get_mode_profile(s),
                    user_ip=user_ip,
                    user_agent=user_agent,
                    referrer=referrer,
                    query_vector=query_vector,
                    kv=kv,
                    bypass_cache=bypass_cache,
                    debug=debug,
                    qualify_suffix=None,
                    speech_language_diag=speech_language_diag,
                    apply_speech_acts=apply_speech_acts,
                )
                return prep, early

        if not hits:
            if trace:
                trace.skip("context_building", "no relevant chunks")
                trace.skip("llm_generation", "fallback without LLM")
            early = RagResult(
                answer=fallback,
                sources=[],
                used_context=False,
                request_id=request_id,
                cache_hit=cache_hit,
                cache_type=cache_type if cache_hit else "none",
                retrieval_ms=retrieval_ms,
                retrieval_debug=retrieval_debug,
                query_intent=query_intent,
                applied_knowledge_config=applied_config_dict,
                cache=cache_info,
                reasoning_diagnostics=speech_language_diag,
            )
            prep = _PreparedStream(
                message=message,
                session_id=session_id,
                request_id=request_id,
                normalized=normalized,
                expanded=expanded,
                fallback=fallback,
                language=language,
                fast=fast,
                hits=[],
                pipeline_context=pipeline_context,
                pipeline_diagnostics=pipeline_diagnostics,
                query_intent=query_intent,
                applied_config=applied_config,
                retrieval_ms=retrieval_ms,
                retrieval_debug=retrieval_debug,
                cache_hit=cache_hit,
                cache_type=cache_type,
                cache_info=cache_info,
                trace=trace,
                gen_system="",
                gen_user="",
                llm_opts={},
                metrics=LlmRuntimeMetrics(),
                prompt_diagnostics={},
                mode_profile=get_mode_profile(s),
                user_ip=user_ip,
                user_agent=user_agent,
                referrer=referrer,
                query_vector=query_vector,
                kv=kv,
                bypass_cache=bypass_cache,
                debug=debug,
                qualify_suffix=None,
                speech_language_diag=speech_language_diag,
                apply_speech_acts=apply_speech_acts,
            )
            return prep, early

        if trace:
            trace.begin("context_building", details={"chunks": len(hits)})
            trace.end("context_building")

        t_prompt = perf_counter()
        org_name = profile.organization_name or profile.site_display_name or "the organization"
        gen_system, gen_user = CompactPromptBuilder.build(
            message=message,
            hits=hits,
            built_context=pipeline_context,
            intent=query_intent,
            settings=s,
            org_name=org_name,
            speech_act_guidance=(
                speech_plan.prompt_guidance if speech_plan else None
            ),
        )
        prompt_build_ms = int((perf_counter() - t_prompt) * 1000)
        prompt_chars = len(gen_system) + len(gen_user) + 2
        llm_opts = resolve_llm_options(s, prompt_chars=prompt_chars)
        if is_overview_intent(query_intent):
            llm_opts["num_predict"] = min(int(llm_opts["num_predict"]), 180)
        mode_profile = get_mode_profile(s)
        metrics = LlmRuntimeMetrics(
            prompt_build_ms=prompt_build_ms,
            prompt_chars=prompt_chars,
            context_chars=len(pipeline_context.prompt_text) if pipeline_context else sum(len(h.text) for h in hits),
            total_tokens_in_estimated=estimate_tokens(prompt_chars),
            model_name=s.llm_model,
            keep_alive=llm_opts.get("keep_alive"),
            num_ctx=llm_opts["num_ctx"],
            num_predict=llm_opts["num_predict"],
            temperature=llm_opts["temperature"],
            top_p=llm_opts.get("top_p"),
            repeat_penalty=llm_opts.get("repeat_penalty"),
            source_count=len(hits),
            llm_mode_profile=llm_opts.get("llm_mode_profile", mode_profile.key),
            polish_mode=eff.get("polish_mode", "off"),
            streaming_enabled=True,
            model_warm=ModelWarmupService.is_warm(s.llm_model),
            model_status=ModelWarmupService.get_status(s.llm_model),
        )
        prompt_diagnostics = metrics.to_dict()
        prompt_diagnostics["timeout_seconds"] = int(
            llm_opts.get("generation_timeout_seconds") or s.ollama_generation_timeout_seconds or 45
        )
        prompt_diagnostics["max_sources"] = eff["max_sources_in_prompt"]
        pre_polish = evaluate_polish(
            s,
            answer="",
            language=language,
            fast_mode=fast,
            generation_ms=0,
            is_overview=is_overview_intent(query_intent),
        )
        prompt_diagnostics["polish_enabled"] = False
        prompt_diagnostics["polish_skip_reason"] = pre_polish.reason
        if debug:
            prompt_diagnostics["system_prompt_preview"] = gen_system[:800]
            prompt_diagnostics["user_prompt_preview"] = gen_user[:2000]
            prompt_diagnostics["context_text_sent"] = (
                pipeline_context.prompt_text if pipeline_context else ""
            )
        if pipeline_diagnostics:
            pipeline_diagnostics.prompt_length = prompt_chars
            pipeline_diagnostics.prompt_diagnostics = prompt_diagnostics

        prep = _PreparedStream(
            message=message,
            session_id=session_id,
            request_id=request_id,
            normalized=normalized,
            expanded=expanded,
            fallback=fallback,
            language=language,
            fast=fast,
            hits=hits,
            pipeline_context=pipeline_context,
            pipeline_diagnostics=pipeline_diagnostics,
            query_intent=query_intent,
            applied_config=applied_config,
            retrieval_ms=retrieval_ms,
            retrieval_debug=retrieval_debug,
            cache_hit=cache_hit,
            cache_type=cache_type,
            cache_info=cache_info,
            trace=trace,
            gen_system=gen_system,
            gen_user=gen_user,
            llm_opts=llm_opts,
            metrics=metrics,
            prompt_diagnostics=prompt_diagnostics,
            mode_profile=mode_profile,
            user_ip=user_ip,
            user_agent=user_agent,
            referrer=referrer,
            query_vector=query_vector,
            kv=kv,
            bypass_cache=bypass_cache,
            debug=debug,
            qualify_suffix=qualify_suffix,
            speech_language_diag=speech_language_diag,
            apply_speech_acts=apply_speech_acts,
        )
        return prep, None
