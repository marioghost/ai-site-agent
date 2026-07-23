"""LLM runtime profiling metrics for diagnostics and server logs."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.llm_runtime_environment import infer_performance_bottleneck
from app.services.ollama_service import OllamaChatResult
from app.utils.time_utils import isoformat_now


@dataclass
class LlmRuntimeMetrics:
    request_start: str = field(default_factory=isoformat_now)
    prompt_build_ms: int = 0
    connection_ms: int | None = None
    ollama_request_ms: int = 0
    time_to_first_token_ms: int | None = None
    generation_ms: int = 0
    total_tokens_in_estimated: int = 0
    total_tokens_out: int = 0
    tokens_per_second: float = 0.0
    model_name: str = ""
    keep_alive: str | None = None
    num_ctx: int = 4096
    num_predict: int = 320
    temperature: float = 0.1
    top_p: float | None = None
    repeat_penalty: float | None = None
    prompt_chars: int = 0
    context_chars: int = 0
    source_count: int = 0
    polish_enabled: bool = False
    polish_ms: int = 0
    model_warm: bool | None = None
    model_status: str | None = None
    llm_mode_profile: str = "fast"
    polish_mode: str = "off"
    retry_happened: bool = False
    streaming_enabled: bool = False
    load_duration_ms: int | None = None
    prompt_eval_duration_ms: int | None = None
    eval_duration_ms: int | None = None
    total_duration_ms: int | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None
    llm_call_count: int = 0
    llm_call_reasons: list[str] = field(default_factory=list)
    performance_bottleneck: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["estimated_tokens"] = self.total_tokens_in_estimated
        data["model"] = self.model_name
        data["tokens_per_sec"] = self.tokens_per_second
        return data

    def apply_ollama_stats(
        self,
        stats: OllamaChatResult,
        *,
        first_token_ms: int | None = None,
        generation_ms: int | None = None,
        gpu_visible: bool = False,
    ) -> None:
        if first_token_ms is not None:
            self.time_to_first_token_ms = first_token_ms
        if generation_ms is not None:
            self.generation_ms = generation_ms
        if stats.connection_ms is not None:
            self.connection_ms = stats.connection_ms
        if stats.load_duration_ns:
            self.load_duration_ms = int(stats.load_duration_ns / 1_000_000)
        if stats.prompt_eval_duration_ns:
            self.prompt_eval_duration_ms = int(stats.prompt_eval_duration_ns / 1_000_000)
        if stats.eval_duration_ns:
            self.eval_duration_ms = int(stats.eval_duration_ns / 1_000_000)
        if stats.total_duration_ns:
            self.total_duration_ms = int(stats.total_duration_ns / 1_000_000)
        if stats.prompt_eval_count:
            self.prompt_eval_count = stats.prompt_eval_count
            self.total_tokens_in_estimated = stats.prompt_eval_count
        if stats.eval_count:
            self.eval_count = stats.eval_count
            self.total_tokens_out = stats.eval_count
        eval_ms = self.eval_duration_ms or self.generation_ms
        if self.total_tokens_out and eval_ms:
            self.tokens_per_second = compute_tokens_per_second(self.total_tokens_out, eval_ms)
        self.performance_bottleneck = infer_performance_bottleneck(
            load_duration_ms=self.load_duration_ms,
            prompt_eval_duration_ms=self.prompt_eval_duration_ms,
            eval_duration_ms=self.eval_duration_ms,
            time_to_first_token_ms=self.time_to_first_token_ms,
            tokens_per_second=self.tokens_per_second,
            gpu_visible=gpu_visible,
        )

    def apply_call_tracker(self, tracker) -> None:
        self.llm_call_count = tracker.count
        self.llm_call_reasons = list(tracker.reasons)

    def log_summary(self) -> str:
        return (
            f"model={self.model_name} mode={self.llm_mode_profile} "
            f"prompt={self.prompt_chars}c ctx={self.context_chars}c "
            f"num_ctx={self.num_ctx} num_predict={self.num_predict} "
            f"build={self.prompt_build_ms}ms conn={self.connection_ms}ms "
            f"ollama={self.ollama_request_ms}ms ttft={self.time_to_first_token_ms}ms "
            f"gen={self.generation_ms}ms tps={self.tokens_per_second} "
            f"load={self.load_duration_ms}ms prompt_eval={self.prompt_eval_duration_ms}ms "
            f"eval={self.eval_duration_ms}ms tokens_out={self.total_tokens_out} "
            f"calls={self.llm_call_count} bottleneck={self.performance_bottleneck}"
        )


def compute_tokens_per_second(output_tokens: int, duration_ms: int) -> float:
    if duration_ms <= 0 or output_tokens <= 0:
        return 0.0
    return round(output_tokens / (duration_ms / 1000.0), 1)
