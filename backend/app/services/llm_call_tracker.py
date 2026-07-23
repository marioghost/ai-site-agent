"""Track LLM calls per chat request for diagnostics."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LlmCallTracker:
    reasons: list[str] = field(default_factory=list)

    def record(self, reason: str) -> None:
        self.reasons.append(reason)

    @property
    def count(self) -> int:
        return len(self.reasons)

    def to_dict(self) -> dict:
        return {
            "llm_call_count": self.count,
            "llm_call_reasons": list(self.reasons),
        }
