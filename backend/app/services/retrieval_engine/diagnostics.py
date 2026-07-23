"""Extended pipeline diagnostics for chat test and observability."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PipelineDiagnostics:
    retrieval_strategy: str = "hybrid"
    expansion_strategy: str = "semantic"
    context_builder_mode: str = "full_content"
    expansion_ms: int = 0
    retrieval_ms: int = 0
    rerank_ms: int = 0
    fusion_ms: int = 0
    context_build_ms: int = 0
    prompt_build_ms: int = 0
    generation_ms: int = 0
    polish_ms: int = 0
    context_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    tokens_per_second: float = 0.0
    selected_chunks: list[dict] = field(default_factory=list)
    rejected_chunks: list[dict] = field(default_factory=list)
    score_breakdowns: list[dict] = field(default_factory=list)
    token_budget: dict | None = None
    context_build_report: dict | None = None
    expansion_rejected_terms: list[str] = field(default_factory=list)
    retry_count: int = 0
    streaming_enabled: bool = False

    def to_dict(self) -> dict:
        return {
            "retrieval_strategy": self.retrieval_strategy,
            "expansion_strategy": self.expansion_strategy,
            "context_builder_mode": self.context_builder_mode,
            "expansion_ms": self.expansion_ms,
            "retrieval_ms": self.retrieval_ms,
            "rerank_ms": self.rerank_ms,
            "fusion_ms": self.fusion_ms,
            "context_build_ms": self.context_build_ms,
            "prompt_build_ms": self.prompt_build_ms,
            "generation_ms": self.generation_ms,
            "polish_ms": self.polish_ms,
            "context_tokens": self.context_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "tokens_per_second": round(self.tokens_per_second, 2),
            "selected_chunks": self.selected_chunks,
            "rejected_chunks": self.rejected_chunks,
            "score_breakdowns": self.score_breakdowns,
            "token_budget": self.token_budget,
            "context_build_report": self.context_build_report,
            "expansion_rejected_terms": self.expansion_rejected_terms,
            "retry_count": self.retry_count,
            "streaming_enabled": self.streaming_enabled,
        }

    @staticmethod
    def estimate_cost(
        *,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
    ) -> float:
        # Local Ollama — nominal cost for observability only.
        _ = model
        return (prompt_tokens + completion_tokens) * 0.000001
