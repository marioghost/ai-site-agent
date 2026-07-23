"""Deterministic pipeline stage state machine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


RETRIEVAL_PIPELINE_ORDER = [
    "intent_detection",
    "query_expansion",
    "chunk_retrieval",
    "document_aggregation",
    "document_scoring",
    "source_intelligence",
    "document_reranking",
    "context_building",
]


@dataclass
class PipelineStageRecord:
    stage: str
    status: StageStatus = StageStatus.PENDING
    duration_ms: int | None = None
    detail: str = ""

    def to_dict(self) -> dict:
        out: dict = {"stage": self.stage, "status": self.status.value}
        if self.duration_ms is not None:
            out["duration_ms"] = self.duration_ms
        if self.detail:
            out["detail"] = self.detail
        return out


@dataclass
class PipelineStateMachine:
    """Tracks retrieval sub-stages with deterministic transitions."""

    stages: dict[str, PipelineStageRecord] = field(default_factory=dict)
    _timers: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in RETRIEVAL_PIPELINE_ORDER:
            self.stages[name] = PipelineStageRecord(stage=name)

    def start(self, stage: str) -> None:
        self._complete_pending_before(stage)
        rec = self.stages.setdefault(stage, PipelineStageRecord(stage=stage))
        rec.status = StageStatus.RUNNING
        self._timers[stage] = perf_counter()

    def complete(self, stage: str, *, detail: str = "") -> PipelineStageRecord:
        rec = self.stages.setdefault(stage, PipelineStageRecord(stage=stage))
        started = self._timers.pop(stage, None)
        if started is not None:
            rec.duration_ms = int((perf_counter() - started) * 1000)
        rec.status = StageStatus.COMPLETED
        rec.detail = detail
        return rec

    def fail(self, stage: str, *, detail: str = "") -> PipelineStageRecord:
        rec = self.stages.setdefault(stage, PipelineStageRecord(stage=stage))
        started = self._timers.pop(stage, None)
        if started is not None:
            rec.duration_ms = int((perf_counter() - started) * 1000)
        rec.status = StageStatus.FAILED
        rec.detail = detail
        return rec

    def skip(self, stage: str, *, detail: str = "") -> PipelineStageRecord:
        rec = self.stages.setdefault(stage, PipelineStageRecord(stage=stage))
        rec.status = StageStatus.SKIPPED
        rec.detail = detail
        self._timers.pop(stage, None)
        return rec

    def _complete_pending_before(self, target: str) -> None:
        if target not in RETRIEVAL_PIPELINE_ORDER:
            return
        idx = RETRIEVAL_PIPELINE_ORDER.index(target)
        for name in RETRIEVAL_PIPELINE_ORDER[:idx]:
            rec = self.stages.get(name)
            if rec and rec.status == StageStatus.PENDING:
                rec.status = StageStatus.SKIPPED
                rec.detail = "auto-skipped before downstream stage"

    def finalize(self) -> None:
        """Mark any still-pending stages as skipped; running stages as completed."""
        seen_running = False
        for name in RETRIEVAL_PIPELINE_ORDER:
            rec = self.stages.get(name)
            if rec is None:
                continue
            if rec.status == StageStatus.RUNNING:
                self.complete(name)
                seen_running = True
            elif rec.status == StageStatus.PENDING and not seen_running:
                rec.status = StageStatus.SKIPPED

    def to_list(self) -> list[dict]:
        self.finalize()
        return [self.stages[n].to_dict() for n in RETRIEVAL_PIPELINE_ORDER if n in self.stages]
