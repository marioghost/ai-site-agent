"""LLM generation with intelligent retry and metrics."""
from __future__ import annotations

from time import perf_counter

from app.core.logging import get_logger
from app.models.settings import Settings
from app.services.answer_completion import preview_prompt
from app.services.context_builder_service import BuiltContext
from app.services.llm_call_tracker import LlmCallTracker
from app.services.llm_mode_service import effective_generation_settings, profile_generation_timeout
from app.services.llm_options_service import estimate_tokens
from app.services.llm_runtime_environment import collect_runtime_environment
from app.services.llm_runtime_profiler import LlmRuntimeMetrics, compute_tokens_per_second
from app.services.ollama_service import OllamaError, OllamaService
from app.services.qdrant_service import SearchHit
from app.services.rag_planning.contracts import AnswerPlan
from app.services.retrieval_engine.context_builder import RetrievalContextBuilder
from app.services.retrieval_engine.prompt_builder import CompactPromptBuilder

logger = get_logger(__name__)


class LlmGenerationService:
    def __init__(self, ollama: OllamaService, settings: Settings) -> None:
        self.ollama = ollama
        self.settings = settings

    def generate(
        self,
        *,
        message: str,
        system_prompt: str,
        user_prompt: str,
        hits: list[SearchHit],
        pipeline_context: BuiltContext | None,
        llm_opts: dict,
        metrics: LlmRuntimeMetrics,
        query_intent: str,
        answer_plan: AnswerPlan | None = None,
        additional_guidance: list[str] | None = None,
        db=None,
        call_tracker: LlmCallTracker | None = None,
    ) -> dict:
        s = self.settings
        eff = effective_generation_settings(s)
        gen_timeout = float(
            llm_opts.get("generation_timeout_seconds") or profile_generation_timeout(s)
        )
        keep_alive = llm_opts.get("keep_alive")
        max_prompt = int(eff.get("llm_max_prompt_chars") or 4500)
        retry_max = min(
            1,
            int(
            llm_opts.get("llm_retry_max_attempts", eff.get("llm_retry_max_attempts", 0)) or 0
            ),
        )
        retry_timeout_only = bool(getattr(s, "llm_retry_on_timeout_only", True))
        tracker = call_tracker or LlmCallTracker()
        t_gen = perf_counter()

        system_prompt, user_prompt = CompactPromptBuilder.truncate_prompts(
            system_prompt, user_prompt, max_prompt
        )

        def _call(system: str, user: str, opts: dict, reason: str) -> tuple:
            tracker.record(reason)
            t_req = perf_counter()
            result = self.ollama.chat(
                model=s.llm_model,
                system_prompt=system,
                user_prompt=user,
                temperature=opts["temperature"],
                max_tokens=opts["num_predict"],
                num_ctx=opts["num_ctx"],
                top_p=opts.get("top_p"),
                repeat_penalty=opts.get("repeat_penalty"),
                timeout=gen_timeout,
                keep_alive=keep_alive,
            )
            ollama_ms = int((perf_counter() - t_req) * 1000)
            return result, ollama_ms

        try:
            chat_result, ollama_ms = _call(
                system_prompt, user_prompt, llm_opts, "rag_generation"
            )
            out = self._success(
                chat_result,
                metrics,
                tracker,
                t_gen,
                ollama_ms,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                retry=False,
            )
            if metrics.output_truncated and retry_max >= 1:
                first_stop_reason = metrics.done_reason or metrics.generation_stop_reason
                return self._retry_compact(
                    message=message,
                    system_prompt=system_prompt,
                    hits=hits,
                    pipeline_context=pipeline_context,
                    llm_opts=llm_opts,
                    metrics=metrics,
                    query_intent=query_intent,
                    answer_plan=answer_plan,
                    additional_guidance=additional_guidance,
                    t_gen=t_gen,
                    max_prompt=max_prompt,
                    gen_timeout=gen_timeout,
                    keep_alive=keep_alive,
                    _call=_call,
                    db=db,
                    tracker=tracker,
                    retry_reason="length_stop",
                    first_stop_reason=first_stop_reason,
                )
            return out
        except OllamaError as exc:
            logger.error("LLM generation failed: %s", exc)
            is_timeout = "timed out" in str(exc).lower() or "timeout" in str(exc).lower()
            metrics.apply_call_tracker(tracker)
            if retry_max < 1 or (retry_timeout_only and not is_timeout):
                return {
                    "error_type": "llm_timeout" if is_timeout else "llm_error",
                    "generation_ms": int((perf_counter() - t_gen) * 1000),
                    "diagnostics": self._prompt_diagnostics(system_prompt, user_prompt, metrics),
                }
            return self._retry_compact(
                message=message,
                system_prompt=system_prompt,
                hits=hits,
                pipeline_context=pipeline_context,
                llm_opts=llm_opts,
                metrics=metrics,
                query_intent=query_intent,
                answer_plan=answer_plan,
                additional_guidance=additional_guidance,
                t_gen=t_gen,
                max_prompt=max_prompt,
                gen_timeout=gen_timeout,
                keep_alive=keep_alive,
                _call=_call,
                db=db,
                tracker=tracker,
            )

    def _retry_compact(
        self,
        *,
        message: str,
        system_prompt: str,
        hits: list[SearchHit],
        pipeline_context: BuiltContext | None,
        llm_opts: dict,
        metrics: LlmRuntimeMetrics,
        query_intent: str,
        answer_plan: AnswerPlan | None,
        additional_guidance: list[str] | None,
        t_gen: float,
        max_prompt: int,
        gen_timeout: float,
        keep_alive: str | None,
        _call,
        db,
        tracker: LlmCallTracker,
        retry_reason: str,
        first_stop_reason: str | None = None,
    ) -> dict:
        compact_hits = self._select_compact_hits(hits, pipeline_context)
        if db is not None:
            builder = RetrievalContextBuilder(db)
            compact_ctx, _ = builder.build(
                compact_hits,
                settings=self.settings,
                user_message=message,
                system_prompt_estimate=system_prompt,
                intent=query_intent,
                max_pages=2,
                max_chunks_per_page=1,
            )
        else:
            compact_ctx, _ = RetrievalContextBuilder().build(
                compact_hits,
                settings=self.settings,
                user_message=message,
                system_prompt_estimate=system_prompt,
                max_pages=2,
            )
        compact_plan = answer_plan.for_compact_retry() if answer_plan else None
        _, compact_user = CompactPromptBuilder.build(
            message=message,
            hits=compact_hits,
            built_context=compact_ctx,
            intent=query_intent,
            settings=self.settings,
            answer_plan=compact_plan,
            additional_guidance=additional_guidance,
        )
        _, compact_user = CompactPromptBuilder.truncate_prompts(
            system_prompt, compact_user, max_prompt
        )
        retry_opts = {
            **llm_opts,
            "num_predict": int(llm_opts["num_predict"]),
            "num_ctx": min(4096, llm_opts["num_ctx"]),
        }
        try:
            chat_result, ollama_ms = _call(
                system_prompt,
                compact_user,
                retry_opts,
                "rag_generation_retry_compact",
            )
            out = self._success(
                chat_result,
                metrics,
                tracker,
                t_gen,
                ollama_ms,
                system_prompt=system_prompt,
                user_prompt=compact_user,
                retry=True,
            )
            out["retry"] = True
            metrics.retry_happened = True
            out["diagnostics"]["retry_reason"] = retry_reason
            out["diagnostics"]["first_stop_reason"] = first_stop_reason
            out["diagnostics"]["retry_stop_reason"] = out["diagnostics"].get("done_reason")
            return out
        except OllamaError as retry_exc:
            metrics.apply_call_tracker(tracker)
            return {
                "error_type": "llm_timeout",
                "generation_ms": int((perf_counter() - t_gen) * 1000),
                "diagnostics": {
                    **self._prompt_diagnostics(system_prompt, compact_user, metrics),
                    "timeout_reason": str(retry_exc),
                    "retry_reason": retry_reason,
                    "first_stop_reason": first_stop_reason,
                    "retry_stop_reason": "error",
                },
                "retry": True,
            }

    @staticmethod
    def _select_compact_hits(
        hits: list[SearchHit],
        pipeline_context: BuiltContext | None,
    ) -> list[SearchHit]:
        if not hits:
            return []
        if pipeline_context and pipeline_context.blocks:
            preferred_ids = [block.source_id for block in pipeline_context.blocks[:3]]
            compact: list[SearchHit] = []
            seen: set[int] = set()
            for source_id in preferred_ids:
                for hit in hits:
                    if hit.source_id == source_id and hit.source_id not in seen:
                        compact.append(hit)
                        seen.add(hit.source_id)
                        break
            if compact:
                return compact
        compact = []
        seen_urls: set[str] = set()
        for hit in hits:
            url = (hit.url or "").strip()
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            compact.append(hit)
            if len(compact) >= 3:
                break
        return compact

    def _success(
        self,
        chat_result,
        metrics: LlmRuntimeMetrics,
        tracker: LlmCallTracker,
        t_gen: float,
        ollama_ms: int,
        system_prompt: str,
        user_prompt: str,
        *,
        retry: bool,
    ) -> dict:
        answer = chat_result.content
        ms = int((perf_counter() - t_gen) * 1000)
        env = collect_runtime_environment()
        metrics.ollama_request_ms = ollama_ms
        metrics.apply_ollama_stats(
            chat_result,
            generation_ms=ms,
            gpu_visible=bool(env.get("nvidia_gpu_visible")),
        )
        if not metrics.total_tokens_out:
            metrics.total_tokens_out = chat_result.eval_count or estimate_tokens(len(answer))
        if not metrics.total_tokens_in_estimated:
            metrics.total_tokens_in_estimated = (
                chat_result.prompt_eval_count or metrics.total_tokens_in_estimated
            )
        if not metrics.tokens_per_second:
            metrics.tokens_per_second = compute_tokens_per_second(
                metrics.total_tokens_out, metrics.eval_duration_ms or ollama_ms or ms
            )
        metrics.retry_happened = retry
        metrics.apply_call_tracker(tracker)
        return {
            "answer": answer,
            "generation_ms": ms,
            "diagnostics": self._prompt_diagnostics(system_prompt, user_prompt, metrics),
        }

    @staticmethod
    def _prompt_diagnostics(
        system_prompt: str,
        user_prompt: str,
        metrics: LlmRuntimeMetrics,
    ) -> dict:
        diagnostics = metrics.to_dict()
        diagnostics["system_prompt_preview"] = system_prompt[:800]
        diagnostics["user_prompt_preview"] = preview_prompt(user_prompt, 2000)
        diagnostics["context_text_sent"] = CompactPromptBuilder.extract_evidence_text(user_prompt)
        return diagnostics
