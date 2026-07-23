"""Controlled Ollama benchmark prompts for admin diagnostics."""
from __future__ import annotations

from time import perf_counter

from app.models.settings import Settings
from app.services.llm_options_service import resolve_llm_options
from app.services.llm_runtime_environment import collect_runtime_environment
from app.services.llm_runtime_profiler import compute_tokens_per_second
from app.services.model_warmup_service import ModelWarmupService
from app.services.ollama_service import OllamaError, OllamaService, OllamaStreamChunk


class LlmBenchmarkService:
    def __init__(self, ollama: OllamaService, settings: Settings) -> None:
        self.ollama = ollama
        self.settings = settings

    def run(self) -> dict:
        model = self.settings.llm_model
        opts = resolve_llm_options(self.settings, prompt_chars=800)
        keep_alive = opts.get("keep_alive")
        timeout = float(self.settings.ollama_generation_timeout_seconds or 60)
        scenarios = [
            ("tiny", "Скажи OK.", "You are concise.", 32),
            (
                "short_uk",
                "Коротко поясни, що таке банк.",
                "Відповідай українською, 2-3 речення.",
                opts["num_predict"],
            ),
            (
                "rag_like",
                "Що таке банк?",
                "Використовуй контекст.\n" + ("X" * 1500),
                min(180, opts["num_predict"]),
            ),
        ]
        results: list[dict] = []
        for key, user_prompt, system_prompt, num_predict in scenarios:
            results.append(
                self._run_scenario(
                    key,
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    opts={**opts, "num_predict": num_predict},
                    timeout=timeout,
                    keep_alive=keep_alive,
                )
            )
        return {
            "model": model,
            "options": opts,
            "model_warm": ModelWarmupService.is_warm(model),
            "warmup_status": ModelWarmupService.get_status(model),
            "environment": collect_runtime_environment(),
            "scenarios": results,
        }

    def _run_scenario(
        self,
        key: str,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        opts: dict,
        timeout: float,
        keep_alive: str | None,
    ) -> dict:
        t0 = perf_counter()
        first_token_ms: int | None = None
        parts: list[str] = []
        stats = None
        error = None
        try:
            for chunk in self.ollama.chat_stream(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=opts["temperature"],
                max_tokens=opts["num_predict"],
                num_ctx=opts["num_ctx"],
                top_p=opts.get("top_p"),
                repeat_penalty=opts.get("repeat_penalty"),
                timeout=timeout,
                keep_alive=keep_alive,
            ):
                if chunk.text:
                    if first_token_ms is None:
                        first_token_ms = int((perf_counter() - t0) * 1000)
                    parts.append(chunk.text)
                if chunk.done and chunk.stats:
                    stats = chunk.stats
        except OllamaError as exc:
            error = str(exc)
        total_ms = int((perf_counter() - t0) * 1000)
        out_tokens = stats.eval_count if stats else max(1, len("".join(parts)) // 4)
        eval_ms = int(stats.eval_duration_ns / 1_000_000) if stats and stats.eval_duration_ns else total_ms
        return {
            "key": key,
            "error": error,
            "answer_preview": "".join(parts)[:200],
            "total_duration_ms": total_ms,
            "load_duration_ms": int(stats.load_duration_ns / 1_000_000) if stats else None,
            "prompt_eval_duration_ms": (
                int(stats.prompt_eval_duration_ns / 1_000_000) if stats else None
            ),
            "eval_duration_ms": int(stats.eval_duration_ns / 1_000_000) if stats else None,
            "prompt_eval_count": stats.prompt_eval_count if stats else None,
            "eval_count": stats.eval_count if stats else out_tokens,
            "tokens_per_second": compute_tokens_per_second(out_tokens, eval_ms),
            "time_to_first_token_ms": first_token_ms,
            "connection_ms": stats.connection_ms if stats else None,
            "model": stats.model if stats else model,
            "options": opts,
        }
